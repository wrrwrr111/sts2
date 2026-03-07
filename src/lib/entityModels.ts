export type MentionableEntity = {
  id: string;
  name?: string | null;
  name_zh?: string | null;
  image_url?: string | null;
};

export type RelicEntity = MentionableEntity & {
  name: string;
  description?: string | null;
  description_zh?: string | null;
  flavor?: string | null;
  flavor_zh?: string | null;
  rarity?: string | null;
  pool?: string | null;
};

export type PotionEntity = MentionableEntity & {
  name: string;
  description?: string | null;
  description_zh?: string | null;
  rarity?: string | null;
};

