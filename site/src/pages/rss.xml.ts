import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import type { APIContext } from "astro";

export async function GET(context: APIContext) {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return rss({
    title: "AI副業ラボ",
    description: "AI×副業の最前線を、AIで稼ぐ高校生が毎日まとめる。",
    site: context.site ?? "https://example.pages.dev",
    items: posts
      .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())
      .map((p) => ({
        link: `/blog/${p.id}/`,
        title: p.data.title,
        description: p.data.description,
        pubDate: p.data.pubDate,
        categories: p.data.tags,
      })),
  });
}
