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
# Sites that block every automated fetch (WSJ answers 401 even to
# facebookexternalhit) can't be fetched; for those, hand-curate an entry
# in data/og-links.json (open the page in a browser, copy its og: values,
# store the preview image as a data: URI — see the encoding snippet in
# tools/make-bsky-fallback.py). A curated entry is used as the fallback
# whenever the live fetch fails.

raise 'og-macro.rb must be required through asciidoctor (-r tools/og-macro.rb)' unless defined? Asciidoctor

require 'base64'
require 'cgi'
require 'date'
require 'json'
require 'net/http'
require 'uri'

OG_DATA = File.expand_path('../data/og-links.json', __dir__).freeze
OG_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

# Follow redirects manually (some hosts redirect without a proxy-safe
# default agent); a handful of hops is plenty for publisher sites.
def og_get(url, hops = 5)
  uri = URI(url)
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = uri.scheme == 'https'
  resp = http.get(uri.request_uri, { 'User-Agent' => OG_UA })
  case resp
  when Net::HTTPRedirection
    return nil if hops.zero?
    # Location may be relative ("docs/x") — resolve against the page URL.
    og_get(URI.join(url, resp['location']).to_s, hops - 1)
  when Net::HTTPOK then resp
  end
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

# Download the og:image as a data: URI, or nil if unfetchable / not
# recognizable as an image.
def og_image_data_uri(url)
  resp = og_get(url)
  return nil unless resp
  mime = resp['content-type'].to_s
  mime = mime.start_with?('image/') ? mime.sub(/;.*/, '') : nil
  return nil unless mime
  "data:#{mime};base64,#{Base64.strict_encode64(resp.body)}"
end

# One entry shaped like an og-links.json entry: {url:, title:, site:,
# date:, description:, image:}.
def og_fetch(url)
  resp = og_get(url)
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

# Two URLs differing only in a trailing slash are the same resource; match
# on the normalized form so a curated entry's canonical URL never fails an
# exact-equality lookup against a hand-typed macro target.
def og_find_entry(target)
  want = target.chomp('/')
  JSON.parse(File.read(OG_DATA))['links'].find { |l| l['url'].chomp('/') == want }
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
  block_macro :og do
    process do |parent, target, attrs|
      entry =
        begin
          og_fetch(target)
        rescue StandardError => e
          fallback = og_find_entry(target)
          raise %(#{e.message} and no curated og-links.json entry for #{target}) unless fallback
          fallback
        end
      create_block parent, :pass, og_card_html(entry), attrs || {}
    end
  end
end
