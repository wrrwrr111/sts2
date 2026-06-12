import {
  closeRichTextTag,
  escapeHtml,
  openRichTextTag,
} from "./richText";

type TextLink = { href: string };
type FormatRelicTextOptions = {
  resolveMention?: (text: string) => TextLink | null;
};

export const formatRelicText = (
  desc: string,
  basePath: string,
  options?: FormatRelicTextOptions,
) => {
  if (!desc) return "";
  const withMentions =
    options?.resolveMention
      ? desc.replace(
          /\[(gold|aqua|blue|green|purple|orange|red|pink)\]([\s\S]*?)\[\/\1\]/gi,
          (full, color, inner) => {
            const content = String(inner ?? "");
            if (!content.trim() || content.includes("[") || content.includes("\n")) {
              return full;
            }
            const linked = options.resolveMention?.(content.trim());
            if (!linked?.href) return full;
            return `[${color}][link=${linked.href}]${content}[/link][/${color}]`;
          },
        )
      : desc;
  const escaped = escapeHtml(withMentions);
  return escaped
    .replace(/\[(passive|evoke)\]/gi, (_, key) => {
      const label = String(key).toUpperCase();
      return `${openRichTextTag(key)}${label}${closeRichTextTag(key)}`;
    })
    .replace(/\[energy:(\d+)\]/gi, (_, raw) => {
      const count = Math.max(0, Math.min(9, Number(raw)));
      if (!count) return "";
      const icon = `${basePath}/images/ui/energy_colorless.png`;
      return `<span class="inline-flex gap-0.5 align-middle">${Array.from({
        length: count,
      })
        .map(
          () =>
            `<img class="inline-block align-text-bottom" style="height:1em;width:1em;margin-bottom:0.1em;filter:drop-shadow(0 1px 1px rgba(0,0,0,0.45));" src="${icon}" alt="" />`,
        )
        .join("")}</span>`;
    })
    .replace(/\[star:(\d+)\]/gi, (_, raw) => {
      const count = Math.max(0, Math.min(9, Number(raw)));
      if (!count) return "";
      const icon = `${basePath}/images/icons/star_icon.png`;
      return `<span class="inline-flex gap-0.5 align-middle">${Array.from({
        length: count,
      })
        .map(
          () =>
            `<img class="inline-block align-text-bottom" style="height:1em;width:1em;margin-bottom:0.1em;filter:drop-shadow(0 1px 1px rgba(0,0,0,0.45));" src="${icon}" alt="" />`,
        )
        .join("")}</span>`;
    })
    .replace(
      /\[([a-zA-Z0-9_]+)(?:=([^\]]+))?\]([\s\S]*?)\[\/\1\]/g,
      (_, tag, arg, inner) => {
        return `${openRichTextTag(tag, arg)}${inner}${closeRichTextTag(tag)}`;
      },
    )
    .replace(/\[([a-zA-Z0-9_]+)(?:=([^\]]+))?\]/g, (_, tag, arg) => {
      return openRichTextTag(tag, arg);
    })
    .replace(/\[\/([a-zA-Z0-9_]+)\]/g, (_, tag) => closeRichTextTag(tag))
    .replace(/\n/g, "<br />");
};
