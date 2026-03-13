export type Card = {
  id: string;
  name: string;
  name_zh: string | null;
  description: string | null;
  description_zh: string | null;
  description_raw?: string | null;
  description_raw_zh?: string | null;
  description_upgraded?: string | null;
  description_upgraded_zh?: string | null;
  cost: number | null;
  is_x_cost: boolean | null;
  is_x_star_cost: boolean | null;
  star_cost: number | null;
  type: string | null;
  rarity: string | null;
  target: string | null;
  color: string | null;
  image_url: string | null;
  beta_image_url: string | null;
  keywords?: string[] | null;
  spawns_cards?: string[] | null;
  upgrade?: Record<string, string | number> | null;
  vars?: Record<string, number> | null;
};

export type Keyword = {
  id: string;
  name: string;
  name_zh: string | null;
  description: string;
  description_zh: string | null;
};

export const TYPE_ZH: Record<string, string> = {
  Attack: "攻击",
  Skill: "技能",
  Power: "能力",
  Status: "状态",
  Curse: "诅咒",
  Quest: "任务",
};
