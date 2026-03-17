-- Seed new categorized breaking news sources
INSERT INTO breaking_rss_sources (id, url, name, platform) VALUES
    (gen_random_uuid(), 'https://feeds.bbci.co.uk/news/rss.xml', 'BBC News', 'BBC'),
    (gen_random_uuid(), 'https://www.aljazeera.com/xml/rss/all.xml', 'Al Jazeera', 'Al_Jazeera'),
    (gen_random_uuid(), 'https://www.france24.com/en/rss', 'France 24', 'France24'),
    (gen_random_uuid(), 'https://www.scmp.com/rss/2/feed', 'SCMP China', 'SCMP'),
    (gen_random_uuid(), 'https://www.straitstimes.com/news/world/rss.xml', 'Straits Times World', 'Straits_Times'),
    (gen_random_uuid(), 'http://www.chinadaily.com.cn/rss/china_rss.xml', 'China Daily', 'China_Daily'),
    (gen_random_uuid(), 'http://www.people.com.cn/rss/politics.xml', 'People''s Daily Politics', 'Peoples_Daily'),
    (gen_random_uuid(), 'http://www.cctv.com/program/rss/02/02/index.xml', 'CCTV', 'CCTV'),
    (gen_random_uuid(), 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml', 'WSJ Markets', 'WSJ'),
    (gen_random_uuid(), 'https://www.ft.com/?format=rss', 'Financial Times', 'FT'),
    (gen_random_uuid(), 'https://www.cnbc.com/id/100003114/device/rss/rss.html', 'CNBC', 'CNBC'),
    (gen_random_uuid(), 'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml', 'NYT Business', 'NYT'),
    (gen_random_uuid(), 'https://news.ycombinator.com/rss', 'Hacker News', 'HN'),
    (gen_random_uuid(), 'https://www.theverge.com/rss/index.xml', 'The Verge', 'Verge'),
    (gen_random_uuid(), 'https://techcrunch.com/feed/', 'TechCrunch', 'TechCrunch')
ON CONFLICT (url) DO NOTHING;
