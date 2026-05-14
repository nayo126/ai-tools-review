import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.string().default("AI副業"),
    tags: z.array(z.string()).default([]),
    keyword: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
