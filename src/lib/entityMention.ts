import type { Lang } from "./i18n";
import { withLang } from "./i18n";
import type { MentionableEntity } from "./entityModels";

export type MentionTarget = {
  href: string;
};

export type MentionEntityType = "card" | "relic" | "potion";
export type MentionEntity = MentionableEntity & {
  type: MentionEntityType;
  href: string;
};

type CreateMentionResolverInput = {
  base: string;
  lang: Lang;
  cards: MentionableEntity[];
  relics: MentionableEntity[];
  potions: MentionableEntity[];
};

export const normalizeMention = (value: string) =>
  value
    .toLowerCase()
    .replace(/[\s`'"“”‘’.,!?;:()[\]{}<>|/\\+\-_=~*&^%$#@，。！？：；、·]+/g, "");

const addEntityMentions = (
  map: Map<string, MentionEntity>,
  items: MentionableEntity[],
  type: MentionEntityType,
  hrefBuilder: (item: MentionableEntity) => string,
  override = false,
) => {
  for (const item of items) {
    const href = hrefBuilder(item);
    const keys = [item.id, item.name, item.name_zh];
    for (const key of keys) {
      if (!key) continue;
      const normalized = normalizeMention(key);
      if (!normalized) continue;
      if (override || !map.has(normalized)) {
        map.set(normalized, {
          ...item,
          type,
          href,
        });
      }
    }
  }
};

export const createMentionEntityResolver = ({
  base,
  lang,
  cards,
  relics,
  potions,
}: CreateMentionResolverInput) => {
  const mentionMap = new Map<string, MentionEntity>();

  addEntityMentions(
    mentionMap,
    cards,
    "card",
    (item) => withLang(`${base}/card/${item.id}`, lang),
  );
  addEntityMentions(
    mentionMap,
    potions,
    "potion",
    (item) => withLang(`${base}/potion/${item.id}`, lang),
    true,
  );
  addEntityMentions(
    mentionMap,
    relics,
    "relic",
    (item) => withLang(`${base}/relic/${item.id}`, lang),
    true,
  );

  return (text: string): MentionEntity | null =>
    mentionMap.get(normalizeMention(text)) ?? null;
};

export const createMentionResolver = (input: CreateMentionResolverInput) => {
  const resolveEntity = createMentionEntityResolver(input);
  return (text: string): MentionTarget | null => {
    const entity = resolveEntity(text);
    return entity ? { href: entity.href } : null;
  };
};

export const extractMentionCandidates = (text: string): string[] => {
  if (!text) return [];
  const out: string[] = [];
  const pattern = /\[([a-zA-Z0-9_]+)\]([\s\S]*?)\[\/\1\]/g;
  let match: RegExpExecArray | null = null;
  while ((match = pattern.exec(text))) {
    const inner = String(match[2] ?? "").trim();
    if (!inner) continue;
    if (inner.includes("[") || inner.includes("\n")) continue;
    out.push(inner);
  }
  return out;
};
