export type Lang = "zh" | "en";

const stripEnPrefix = (pathname: string) => {
  if (pathname === "/en") return "/";
  if (pathname.startsWith("/en/")) return pathname.slice(3) || "/";
  return pathname;
};

export const getLangFromUrl = (url: URL): Lang => {
  const queryLang = url.searchParams.get("lang");
  if (queryLang === "en") return "en";
  if (queryLang === "zh") return "zh";
  return url.pathname === "/en" || url.pathname.startsWith("/en/")
    ? "en"
    : "zh";
};

export const withLang = (path: string, lang: Lang): string => {
  const [rawPathname, rawQuery] = path.split("?");
  const pathname = rawPathname.startsWith("/") ? rawPathname : `/${rawPathname}`;
  const basePath = stripEnPrefix(pathname);
  const targetPath =
    lang === "en" ? (basePath === "/" ? "/en" : `/en${basePath}`) : basePath;
  return rawQuery ? `${targetPath}?${rawQuery}` : targetPath;
};

export const pickText = (
  lang: Lang,
  zh: string | null | undefined,
  en: string | null | undefined,
  fallback = "",
) => {
  const first = lang === "en" ? en : zh;
  const second = lang === "en" ? zh : en;
  return first ?? second ?? fallback;
};
