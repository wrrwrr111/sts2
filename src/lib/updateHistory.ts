import type { Lang } from "./i18n";

type DiffValue = string | number | boolean | null | DiffValue[] | {
  [key: string]: DiffValue;
};

type DiffChange = {
  field: string;
  old: DiffValue;
  new: DiffValue;
};

type DiffChangedEntity = {
  id: string;
  name?: string | null;
  changes?: DiffChange[] | null;
};

type DiffCategory = {
  id: string;
  name?: string | null;
  changed?: DiffChangedEntity[] | null;
};

type DiffReport = {
  created_at?: string | null;
  release_date?: string | null;
  from_ref?: string | null;
  to_ref?: string | null;
  from_version?: string | null;
  to_version?: string | null;
  from_label?: string | null;
  to_label?: string | null;
  game_version?: string | null;
  categories?: DiffCategory[] | null;
};

export type UpdateHistoryChange = {
  field: string;
  oldValue: string;
  newValue: string;
};

export type UpdateHistoryEntry = {
  key: string;
  createdAt: string | null;
  releaseDate: string | null;
  fromRef: string | null;
  toRef: string | null;
  fromVersion: string | null;
  toVersion: string | null;
  fromLabel: string | null;
  toLabel: string | null;
  gameVersion: string | null;
  changes: UpdateHistoryChange[];
};

const reportModules = import.meta.glob("../../reports/diff/*.json", {
  eager: true,
  import: "default",
}) as Record<string, DiffReport>;

const normalizeId = (value: string) => value.trim().toLowerCase();

const normalizeValue = (value: DiffValue): string => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
};

const reports = Object.entries(reportModules)
  .map(([path, report]) => ({
    path,
    report,
  }))
  .sort((a, b) => {
    const at = Date.parse(a.report.release_date ?? a.report.created_at ?? "");
    const bt = Date.parse(b.report.release_date ?? b.report.created_at ?? "");
    if (Number.isFinite(at) && Number.isFinite(bt) && at !== bt) {
      return bt - at;
    }
    return b.path.localeCompare(a.path);
  });

const isInternalCurrentComparison = (report: DiffReport) =>
  report.from_ref === "HEAD" && report.to_ref === "current";

export const getEntityUpdateHistory = (
  categoryId: string,
  entityId: string,
): UpdateHistoryEntry[] => {
  const normalizedCategoryId = normalizeId(categoryId);
  const normalizedEntityId = normalizeId(entityId);

  return reports.flatMap(({ path, report }, reportIndex) => {
    const category = (report.categories ?? []).find(
      (item) => normalizeId(item.id) === normalizedCategoryId,
    );
    if (!category) return [];

    const entity = (category.changed ?? []).find(
      (item) => normalizeId(item.id) === normalizedEntityId,
    );
    if (!entity || !entity.changes || entity.changes.length === 0) return [];

    const nextOlderReport = reports[reportIndex + 1]?.report;
    const inferredFromVersion = isInternalCurrentComparison(report)
      ? (nextOlderReport?.to_version ?? nextOlderReport?.game_version ?? null)
      : null;
    const toVersion = report.to_version ?? report.game_version ?? null;
    const fromVersion = report.from_version ?? inferredFromVersion;

    return [
      {
        key: `${path}:${entity.id}`,
        createdAt: report.created_at ?? null,
        releaseDate: report.release_date ?? null,
        fromRef: report.from_ref ?? null,
        toRef: report.to_ref ?? null,
        fromVersion,
        toVersion,
        fromLabel: report.from_label ?? fromVersion,
        toLabel: report.to_label ?? toVersion,
        gameVersion: report.game_version ?? null,
        changes: entity.changes.map((change) => ({
          field: change.field,
          oldValue: normalizeValue(change.old),
          newValue: normalizeValue(change.new),
        })),
      },
    ];
  });
};

const fieldLabelMap: Record<string, { en: string; zh: string }> = {
  act: { en: "Act", zh: "章节" },
  color: { en: "Color", zh: "颜色" },
  description: { en: "Description", zh: "描述" },
  description_raw: { en: "Raw Description", zh: "原始描述" },
  description_raw_zh: { en: "Raw Description (ZH)", zh: "中文原始描述" },
  description_upgraded: { en: "Upgraded Description", zh: "升级描述" },
  description_upgraded_zh: { en: "Upgraded Description (ZH)", zh: "中文升级描述" },
  description_zh: { en: "Description (ZH)", zh: "中文描述" },
  flavor: { en: "Flavor", zh: "风味文本" },
  flavor_zh: { en: "Flavor (ZH)", zh: "中文风味文本" },
  max_energy: { en: "Max Energy", zh: "最大能量" },
  name: { en: "Name", zh: "名称" },
  name_zh: { en: "Name (ZH)", zh: "中文名称" },
  orb_slots: { en: "Orb Slots", zh: "充能球位" },
  pool: { en: "Pool", zh: "遗物池" },
  rarity: { en: "Rarity", zh: "稀有度" },
  starting_gold: { en: "Starting Gold", zh: "初始金币" },
  starting_hp: { en: "Starting HP", zh: "初始生命" },
  type: { en: "Type", zh: "类型" },
  unlocks_after: { en: "Unlock After", zh: "解锁条件" },
};

export const getUpdateHistoryFieldLabel = (field: string, lang: Lang): string => {
  const mapped = fieldLabelMap[field];
  if (mapped) return mapped[lang];

  return field
    .split("_")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
};
