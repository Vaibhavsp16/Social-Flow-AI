const db = globalThis.__B44_DB__ || { auth:{ isAuthenticated: async()=>false, me: async()=>null }, entities:new Proxy({}, { get:()=>({ filter:async()=>[], get:async()=>null, create:async()=>({}), update:async()=>({}), delete:async()=>({}) }) }), integrations:{ Core:{ UploadFile:async()=>({ file_url:'' }) } } };

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.44';

const INDUSTRY_PROMPTS = {
  "Real Estate": {
    focus: ["Location", "Amenities", "Lifestyle", "Investment", "Property USP", "Configuration", "Architecture"],
    tone: "aspirational, trustworthy, and premium real-estate authority",
    audience: "homebuyers, property investors, and families seeking their next home",
    strategy: "Rotate through location advantages, lifestyle benefits, investment value, and unique property features. Use architecture and configuration details to build desire. Always ground claims in the reference material when provided.",
    hashtags: ["RealEstate", "PropertyInvestment", "LuxuryLiving", "DreamHome", "RealEstateIndia", "HomeBuying", "PropertyLaunch"]
  },
  "Jewellery": {
    focus: ["Craftsmanship", "Luxury", "Occasion", "Design", "Materials", "Emotion", "Gifting"],
    tone: "elegant, emotive, and luxurious",
    audience: "jewellery connoisseurs, gift buyers, and bridal/occasion shoppers",
    strategy: "Emphasize craftsmanship, precious materials, design heritage, and the emotion behind gifting and special occasions. Weave in the story of each piece.",
    hashtags: ["Jewellery", "LuxuryJewellery", "FineJewellery", "JewelleryDesign", "GoldJewellery", "DiamondJewellery", "JewelleryLover"]
  },
  "Product - Perfume": {
    focus: ["Fragrance notes", "Mood", "Personality", "Lifestyle", "Luxury", "Occasion", "Sensory language"],
    tone: "sensory, evocative, and sophisticated",
    audience: "fragrance enthusiasts and lifestyle/luxury consumers",
    strategy: "Use rich sensory language around fragrance notes (top/heart/base), mood, personality, and occasion. Make the scent tangible through words. Evoke the feeling of wearing it.",
    hashtags: ["Perfume", "Fragrance", "LuxuryFragrance", "PerfumeLover", "SignatureScent", "EauDeParfum", "FragranceFamily"]
  },
  "FMCG - Food": {
    focus: ["Taste", "Ingredients", "Convenience", "Family", "Consumption occasions", "Product benefits", "Food appeal"],
    tone: "appetizing, warm, relatable, and energetic",
    audience: "families, everyday consumers, and food lovers",
    strategy: "Make the food irresistible with vivid taste descriptions, ingredient stories, family and consumption occasions, and clear product benefits. Drive trial and repeat.",
    hashtags: ["Food", "FoodLover", "Tasty", "FMCG", "Foodie", "SnackTime", "MadeWithLove"]
  }
};

const CONTENT_TYPE_GUIDE = {
  "Single Post": "a single image post with a scroll-stopping caption",
  "Reel": "a short vertical reel — caption should hint at motion, sound, and a hook in the first 3 seconds",
  "Carousel": "a multi-slide carousel — caption should tease the swipe journey and summarize the slides",
  "Story": "a 24-hour story — caption should be punchy, urgent, and interactive (poll/question/CTA sticker)"
};

export default async function(req: Request): Promise<Response> {
  try {
    const base44 = createClientFromRequest(req);
    const user = await db.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    const body = await req.json();
    const { industry, duration, numPosts, contentType, referenceFileUrls } = body || {};

    if (!industry || !INDUSTRY_PROMPTS[industry]) {
      return Response.json({ error: 'A valid industry is required' }, { status: 400 });
    }
    if (!duration) {
      return Response.json({ error: 'A duration is required' }, { status: 400 });
    }
    const postCount = Number(numPosts);
    if (!postCount || postCount < 1 || postCount > 20) {
      return Response.json({ error: 'A valid number of posts is required' }, { status: 400 });
    }
    const format = contentType && CONTENT_TYPE_GUIDE[contentType] ? contentType : "Single Post";

    const config = INDUSTRY_PROMPTS[industry];
    const files = Array.isArray(referenceFileUrls) ? referenceFileUrls.filter(Boolean) : [];

    const prompt = `You are an elite social-media content strategist and copywriter specializing in the ${industry} industry.

Generate a complete ${duration} social-media content plan with EXACTLY ${postCount} posts for the "${format}" format (${CONTENT_TYPE_GUIDE[format]}).

INDUSTRY-SPECIFIC REQUIREMENTS — ${industry}:
- Focus areas to rotate across the posts (do not repeat the same focus twice in a row): ${config.focus.join(", ")}.
- Tone of voice: ${config.tone}.
- Target audience: ${config.audience}.
- Content strategy: ${config.strategy}

GENERAL REQUIREMENTS:
- Every caption must be distinct, platform-native (Instagram-first), and crafted specifically for ${industry}. Do NOT write generic content — each post must clearly read as ${industry} through its vocabulary, references, and angle.
- Each caption needs a strong hook in the first line, a compelling body, and a clear call-to-action.
- Space the posts realistically across the ${duration} period starting from today (2026-08-31). Give each a specific date.
- Vary the focus area, angle, and CTA across posts so the plan feels like a real calendar, not a template.
- imageDirection must be a vivid, art-direction brief: composition, subject, mood, lighting, props, color palette, and style — detailed enough for a designer or AI image generator to execute.
- hashtags: 8 to 12 tags per post, mixing evergreen industry tags (e.g. ${config.hashtags.slice(0, 4).join(", ")}) with post-specific and occasion-specific tags. No duplicates within a post.${files.length ? `\n\nREFERENCE MATERIAL: Use the following uploaded reference files as authoritative context about the brand, products, and messaging. Align tone, product names, and details with them: ${files.join(", ")}` : ""}

Return ONLY a JSON object matching the provided schema. Do not include any commentary.`;

    const result = await db.asServiceRole.integrations.Core.InvokeLLM({
      prompt,
      file_urls: files.length ? files : undefined,
      response_json_schema: {
        type: "object",
        properties: {
          posts: {
            type: "array",
            items: {
              type: "object",
              properties: {
                postNumber: { type: "number" },
                date: { type: "string" },
                focusArea: { type: "string" },
                caption: { type: "string" },
                imageDirection: { type: "string" },
                hashtags: { type: "array", items: { type: "string" } }
              },
              required: ["postNumber", "date", "caption", "imageDirection", "hashtags"]
            }
          }
        },
        required: ["posts"]
      }
    });

    const posts = Array.isArray(result?.posts) ? result.posts : [];
    return Response.json({ posts });
  } catch (error) {
    return Response.json({ error: error.message || 'Failed to generate content' }, { status: 500 });
  }
}