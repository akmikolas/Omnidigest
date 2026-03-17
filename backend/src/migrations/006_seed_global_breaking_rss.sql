-- Migration: Seed additional global breaking RSS sources
-- 迁移：添加更多全球突发新闻 RSS 数据源

-- Asia (亚洲)
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
(gen_random_uuid(), 'https://china.kyodonews.net/rss/news.xml', '共同网 (Kyodo News)', '日本'),
(gen_random_uuid(), 'https://en.yna.co.kr/RSS/news.xml', '韩联社 (Yonhap News)', '韩国'),
(gen_random_uuid(), 'https://www.zaobao.com.sg/rss/realtime/china', '联合早报 (Lianhe Zaobao)', '新加坡'),
(gen_random_uuid(), 'https://en.vietnamplus.vn/rss/politics.rss', '越南通讯社 (VNA)', '越南'),
(gen_random_uuid(), 'https://sputniknews.cn/export/rss2/archive/index.xml', '卫星通讯社 (Sputnik)', '俄罗斯')
ON CONFLICT (url) DO NOTHING;

-- Europe (欧洲)
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
(gen_random_uuid(), 'https://www.reutersagency.com/feed/?best-types=top-news&post_type=best', '路透社 (Reuters)', '英国'),
(gen_random_uuid(), 'https://rss.dw.com/rdf/rss-en-all', '德国之声 (DW)', '德国'),
(gen_random_uuid(), 'https://newsroom.consilium.europa.eu/rss/all', '欧盟理事会 (EU Council)', '欧盟'),
(gen_random_uuid(), 'https://www.swissinfo.ch/eng/rss', '瑞士资讯 (Swissinfo)', '瑞士')
ON CONFLICT (url) DO NOTHING;

-- Americas (美洲)
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
(gen_random_uuid(), 'https://apnews.com/hub/world-news.rss', '美联社 (Associated Press)', '美国'),
(gen_random_uuid(), 'https://www.voanews.com/api/z$ite_oytiv', '美国之音 (VOA)', '美国'),
(gen_random_uuid(), 'https://www.cbc.ca/webfeed/rss/rss-topstories', '加拿大广播公司 (CBC)', '加拿大'),
(gen_random_uuid(), 'https://agenciabrasil.ebc.com.br/rss/geral/feed.xml', '巴西通讯社 (Agência Brasil)', '巴西')
ON CONFLICT (url) DO NOTHING;

-- Middle East & Africa (中东与非洲)
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
(gen_random_uuid(), 'https://www.timesofisrael.com/feed/', '以色列时报 (Times of Israel)', '以色列'),
(gen_random_uuid(), 'https://www.aa.com.tr/en/rss/default?cat=world', '阿纳多卢通讯社 (Anadolu Agency)', '土耳其'),
(gen_random_uuid(), 'http://feeds.news24.com/articles/news24/TopStories/rss', 'News24', '南非')
ON CONFLICT (url) DO NOTHING;

-- International Organizations (国际组织)
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
(gen_random_uuid(), 'https://news.un.org/feed/subscribe/en/news/all/rss.xml', '联合国 (UN News)', '联合国'),
(gen_random_uuid(), 'https://www.who.int/rss-feeds/news-english.xml', '世界卫生组织 (WHO)', 'WHO'),
(gen_random_uuid(), 'https://www.imf.org/en/News/RSS', '国际货币基金组织 (IMF)', 'IMF')
ON CONFLICT (url) DO NOTHING;
