export const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export const escapeHtmlAttribute = (value: string) =>
  escapeHtml(value).replace(/"/g, "&quot;");

type RichTextTagOptions = {
  extraClasses?: string[];
  attributes?: Record<string, string>;
};

const getTagDefinition = (tag: string, arg?: string) => {
  const normalizedTag = tag.toLowerCase();
  if (normalizedTag === "b") {
    return { element: "strong", classes: ["inline-block"] };
  }
  if (normalizedTag === "i") {
    return { element: "em", classes: ["inline-block"] };
  }
  if (normalizedTag === "u") {
    return { element: "span", classes: ["inline-block", "underline"] };
  }
  if (normalizedTag === "font_size") {
    const parsed = Number(arg ?? 0);
    const px = Number.isFinite(parsed)
      ? Math.max(10, Math.min(48, parsed))
      : 16;
    return {
      element: "span",
      classes: ["inline-block", "align-baseline"],
      attributes: { style: `font-size:${px}px;line-height:1.15;` },
    };
  }

  const colorClasses: Record<string, string> = {
    gold: "text-[#ffd38c]",
    red: "text-[#ff7b7b]",
    blue: "text-[#7fb8ff]",
    green: "text-[#86e3a0]",
    purple: "text-[#b89bff]",
    orange: "text-[#ffb46a]",
    aqua: "text-[#7fe3ff]",
    pink: "text-[#ff9bd0]",
  };
  if (colorClasses[normalizedTag]) {
    return {
      element: "span",
      classes: ["inline-block", colorClasses[normalizedTag]],
    };
  }
  if (normalizedTag === "rainbow") {
    return {
      element: "span",
      classes: [
        "inline-block",
        "text-transparent",
        "[background:linear-gradient(90deg,#ff6b6b,#ffd93d,#6bffb6,#6bc7ff,#b56bff)]",
        "[-webkit-background-clip:text]",
      ],
    };
  }
  if (normalizedTag === "amount") {
    return {
      element: "span",
      classes: ["inline-block", "text-[#ffe6b0]", "font-semibold"],
    };
  }
  if (normalizedTag === "passive" || normalizedTag === "evoke") {
    return {
      element: "span",
      classes: [
        "inline-block",
        "text-[#bfe5ff]",
        "uppercase",
        "tracking-[0.08em]",
        "text-[0.85em]",
      ],
    };
  }
  if (normalizedTag === "sine") {
    return {
      element: "span",
      classes: ["inline-block", "animate-bounce"],
    };
  }
  if (normalizedTag === "jitter") {
    return {
      element: "span",
      classes: ["inline-block", "animate-pulse"],
    };
  }
  if (normalizedTag === "link") {
    return {
      element: "a",
      classes: [
        "inline-block",
        "underline",
        "decoration-dotted",
        "underline-offset-2",
        "hover:text-[#fff5df]",
        "transition-colors",
      ],
      attributes: { href: arg || "#" },
    };
  }
  return { element: "span", classes: ["inline-block"] };
};

export const openRichTextTag = (
  tag: string,
  arg?: string,
  options: RichTextTagOptions = {},
) => {
  const definition = getTagDefinition(tag, arg);
  const classes = [...definition.classes, ...(options.extraClasses ?? [])];
  const attributes = {
    ...definition.attributes,
    ...options.attributes,
  };
  const serializedAttributes = Object.entries(attributes)
    .map(
      ([name, value]) =>
        ` ${name}="${escapeHtmlAttribute(value)}"`,
    )
    .join("");
  return `<${definition.element} class="${classes.join(" ")}"${serializedAttributes}>`;
};

export const closeRichTextTag = (tag: string) => {
  const normalizedTag = tag.toLowerCase();
  if (normalizedTag === "b") return "</strong>";
  if (normalizedTag === "i") return "</em>";
  if (normalizedTag === "link") return "</a>";
  return "</span>";
};
