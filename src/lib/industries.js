import { Building2, Gem, Sparkles, UtensilsCrossed } from "lucide-react";

export const INDUSTRIES = [
  {
    id: "Real Estate",
    name: "Real Estate",
    tagline: "Properties, lifestyle & investment",
    focus: ["Location", "Amenities", "Lifestyle", "Investment", "Property USP", "Configuration", "Architecture"],
    gradient: "from-sky-500 to-indigo-600",
    ring: "ring-sky-400",
    soft: "bg-sky-50",
    text: "text-sky-700",
    icon: Building2
  },
  {
    id: "Jewellery",
    name: "Jewellery",
    tagline: "Craftsmanship, luxury & emotion",
    focus: ["Craftsmanship", "Luxury", "Occasion", "Design", "Materials", "Emotion", "Gifting"],
    gradient: "from-amber-500 to-rose-500",
    ring: "ring-amber-400",
    soft: "bg-amber-50",
    text: "text-amber-700",
    icon: Gem
  },
  {
    id: "Product - Perfume",
    name: "Perfume",
    tagline: "Fragrance, mood & sensory luxury",
    focus: ["Fragrance notes", "Mood", "Personality", "Lifestyle", "Luxury", "Occasion", "Sensory language"],
    gradient: "from-fuchsia-500 to-purple-600",
    ring: "ring-fuchsia-400",
    soft: "bg-fuchsia-50",
    text: "text-fuchsia-700",
    icon: Sparkles
  },
  {
    id: "FMCG - Food",
    name: "FMCG / Food",
    tagline: "Taste, ingredients & family moments",
    focus: ["Taste", "Ingredients", "Convenience", "Family", "Consumption occasions", "Product benefits", "Food appeal"],
    gradient: "from-orange-500 to-red-500",
    ring: "ring-orange-400",
    soft: "bg-orange-50",
    text: "text-orange-700",
    icon: UtensilsCrossed
  }
];

export const DURATIONS = [
  { id: "1 Week", label: "1 Week", posts: 3, description: "Quick burst" },
  { id: "2 Weeks", label: "2 Weeks", posts: 6, description: "Steady rhythm" },
  { id: "1 Month", label: "1 Month", posts: 12, description: "Full calendar" }
];

export const CONTENT_TYPES = ["Single Post", "Reel", "Carousel", "Story"];