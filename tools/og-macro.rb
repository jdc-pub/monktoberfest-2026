# frozen_string_literal: true

# og-macro.rb — native `og::URL[]` block macro: an OpenGraph link-preview
# card, fetched live at conversion time from the target page. Load it
# with:  asciidoctor-revealjs -r tools/og-macro.rb
#
# The card markup is emitted during conversion, so unlike a runtime driver
# there is no script to fail and no fallback stand-in — the HTML is always
# in the slide. Card images are inlined as data: URIs so they render
# offline and survive tools/inline.py. Styling lives in
# css/theme-override.css (§ "OpenGraph link cards").
#
# Unfetchable pages (WSJ answers 401 even to facebookexternalhit; WaPo
# times out) can be hand-specified instead: give title= and the fetch is
# skipped entirely —
#
#   og::URL[title="The Title", site="The Site", date=YYYY-MM-DD,
#           description="...", image=img/local.jpg]
#
# site, date and description are optional; image accepts a local path
# (relative to the document directory) or an http(s) URL.
#
# Pages whose og:image is a generic placeholder (NPR answers every fetch,
# but with its facebook-default logo) can override just the image with
# the same image attribute; the rest of the metadata still comes from
# the live fetch.
#
# Fetches are cached in data/og-cache.json (keyed by URL) and run in
# parallel via a preprocessor pass, so repeat builds are instant and the
# first build pays the network cost once. The cache is derived data —
# delete it anytime; set OG_REFRESH=1 to rebuild it from the network.

raise 'og-macro.rb must be required through asciidoctor (-r tools/og-macro.rb)' unless defined? Asciidoctor

require 'base64'
require 'cgi'
require 'date'
require 'json'
require 'net/http'
require 'uri'

OG_UAS = ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
          'facebookexternalhit/1.1'].freeze

IMAGE_MIME_BY_EXT = { 'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png',
                      'webp' => 'image/webp', 'gif' => 'image/gif' }.freeze

OG_CACHE_PATH = File.expand_path('../data/og-cache.json', __dir__).freeze
OG_REFRESH = ENV['OG_REFRESH'] == '1'
OG_CACHE = begin
  OG_REFRESH ? {} : JSON.parse(File.read(OG_CACHE_PATH))
rescue Errno::ENOENT, JSON::ParserError
  {}
end
OG_CACHE_MUTEX = Mutex.new
# Fetch failures are memoized in memory only — never persisted, so a
# transient network failure never poisons future builds.
OG_CACHE_ERRORS = {}

# Cached entry lookup by URL; two URLs differing only in a trailing slash
# are the same resource.
def og_fetch_cached(url)
  key = url.chomp('/')
  hit = OG_CACHE_MUTEX.synchronize do
    raise OG_CACHE_ERRORS.fetch(key) if OG_CACHE_ERRORS.key?(key)
    OG_CACHE[key]
  end
  return hit unless hit.nil?
  entry = og_fetch(url)
  OG_CACHE_MUTEX.synchronize { OG_CACHE[key] = entry }
  entry
rescue StandardError => e
  OG_CACHE_MUTEX.synchronize { OG_CACHE_ERRORS[key] = e }
  raise
end

at_exit do
  next if OG_CACHE.empty?
  require 'fileutils'
  FileUtils.mkdir_p(File.dirname(OG_CACHE_PATH))
  File.write(OG_CACHE_PATH, JSON.pretty_generate(OG_CACHE))
end

# Follow redirects manually (some hosts redirect without a proxy-safe
# default agent); a handful of hops is plenty for publisher sites.
def og_get(url, ua = OG_UAS[0], hops = 5)
  uri = URI(url)
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = uri.scheme == 'https'
  resp = http.get(uri.request_uri, { 'User-Agent' => ua })
  case resp
  when Net::HTTPRedirection
    return nil if hops.zero?
    # Location may be relative ("docs/x") — resolve against the page URL.
    og_get(URI.join(url, resp['location']).to_s, ua, hops - 1)
  when Net::HTTPOK then resp
  end
end

# Some publishers 403 browser UAs but serve OpenGraph to social-preview
# bots (nytimes.com); others block everything (see the WSJ note above).
def og_get_any(url)
  OG_UAS.each do |ua|
    resp = og_get(url, ua)
    return resp if resp
  end
  nil
end

def og_meta(html)
  html = html.force_encoding(Encoding::UTF_8)
  meta = {}
  html.scan(%r{<meta\b[^>]*>}i).each do |tag|
    key = tag[/\bproperty=["']([^"']+)["']/i, 1] || tag[/\bname=["']([^"']+)["']/i, 1]
    content = tag[/\bcontent=["']([^"']*)["']/i, 1]
    meta[key] = content if key && content
  end
  meta['<title>'] = html[%r{<title>(.*?)</title>}im, 1]
  meta
end

# Download a remote image or read a local file, and return it as a
# data: URI; nil if unfetchable / not recognizable as an image.
def og_image_data_uri(spec)
  if File.file?(spec)
    body = File.binread(spec)
    ext = spec[/\.([^.\/]+)\z/, 1].to_s.downcase
    mime = IMAGE_MIME_BY_EXT[ext] or raise %(unknown image extension: #{spec})
  else
    resp = og_get_any(spec)
    return nil unless resp
    mime = resp['content-type'].to_s
    mime = mime.start_with?('image/') ? mime.sub(/;.*/, '') : nil
    return nil unless mime
    body = resp.body
  end
  "data:#{mime};base64,#{Base64.strict_encode64(body)}"
end

# One entry shaped like an og-links.json entry: {url:, title:, site:,
# date:, description:, image:}.
def og_fetch(url)
  resp = og_get_any(url)
  raise %(page unfetchable: #{url}) unless resp
  m = og_meta(resp.body)
  title = m['og:title'] || m['twitter:title'] || m['<title>'].to_s.strip
  raise %(page exposes no og:/twitter:/<title> text: #{url}) if title.empty?
  entry = { 'url' => url, 'title' => title }
  desc = (m['og:description'] || m['twitter:description']).to_s
  entry['description'] = desc.gsub(/\s+/, ' ').strip unless desc.empty?
  entry['site'] = m['og:site_name'] || URI(url).host
  published = m['article:published_time'] || m['og:updated_time']
  entry['date'] = published[0, 10] if published
  uri = m['og:image'] || m['twitter:image']
  entry['image'] = og_image_data_uri(uri) if uri
  entry
end

def og_card_html(entry)
  url = entry.fetch('url')
  title = CGI.escapeHTML entry['title'].to_s
  media = entry['image'] ? %(<img class="og-card-media" src="#{entry['image']}" alt="#{title}">) : ''
  desc = entry['description'] ? %(<span class="og-card-desc">#{CGI.escapeHTML entry['description']}</span>) : ''
  host = URI(url).host.sub(/\Awww\./, '')
  date = entry['date'] ? Date.parse(entry['date']).strftime('%B %-d, %Y') : nil
  meta = [host, date].compact.join(' · ')
  <<~HTML
    <a class="og-card" href="#{CGI.escapeHTML url}" target="_blank" rel="noopener">
    #{media}
      <span class="og-card-body">
        <span class="og-card-site">#{CGI.escapeHTML entry['site'].to_s}</span>
        <span class="og-card-title">#{title}</span>
    #{desc}
        <span class="og-card-host">#{CGI.escapeHTML meta}</span>
      </span>
    </a>
  HTML
end

Asciidoctor::Extensions.register do
  # Prime the cache in parallel before any og:: macro runs sequentially
  # during conversion. Only plain `og::URL[]` macros are prefetched —
  # hand-specified cards (title=...) are unfetchable by design and their
  # image= overrides are fetched in-macro.
  preprocessor do
    process do |doc|
      source = doc.reader.read_lines
      urls = source.join("\n").scan(/^og::(https?:\/\/[^\s\[]+)\[\]/).flatten
                   .map { |u| u.chomp('/') }.uniq
      urls -= OG_CACHE.keys unless OG_REFRESH
      urls.each_slice(8).flat_map { |batch|
        batch.map { |u| Thread.new { og_fetch_cached(u) rescue nil } }
      }.each(&:join)
      ::Asciidoctor::Reader.new(source, doc.file)
    end
  end

  block_macro :og do
    process do |parent, target, attrs|
      attrs = (attrs || {}).dup
      image_url = attrs.delete('image')
      image_url = File.expand_path(image_url, parent.document.base_dir) if image_url && !image_url.start_with?(%r{https?://})
      entry =
        if attrs['title']
          {
            'url' => target,
            'title' => attrs.delete('title'),
            'site' => attrs.delete('site'),
            'description' => attrs.delete('description'),
            'date' => attrs.delete('date'),
          }.compact
        else
          og_fetch_cached(target)
        end
      entry['image'] = og_image_data_uri(image_url) if image_url
      create_block parent, :pass, og_card_html(entry), attrs
    end
  end
end
