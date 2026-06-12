type StoredListState = {
  search: string;
  groups: Record<string, string[]>;
  scrollY: number;
};

type ListFilterStateOptions = {
  searchEl: HTMLInputElement | null;
  resetEl: HTMLButtonElement | null;
};

const getStorageKey = () => `sts2:list-state:${window.location.pathname}`;

const readState = (): StoredListState | null => {
  try {
    const raw = sessionStorage.getItem(getStorageKey());
    return raw ? (JSON.parse(raw) as StoredListState) : null;
  } catch {
    return null;
  }
};

export const setupListFilterState = ({
  searchEl,
  resetEl,
}: ListFilterStateOptions) => {
  const groups = Array.from(
    document.querySelectorAll<HTMLElement>("[data-filter-group]"),
  );

  const saveState = () => {
    const selectedGroups = Object.fromEntries(
      groups.map((group) => [
        group.dataset.filterGroup ?? "",
        Array.from(
          group.querySelectorAll<HTMLButtonElement>(
            '[data-filter-value][aria-pressed="true"]',
          ),
        )
          .map((button) => button.dataset.filterValue ?? "")
          .filter(Boolean),
      ]),
    );

    try {
      sessionStorage.setItem(
        getStorageKey(),
        JSON.stringify({
          search: searchEl?.value ?? "",
          groups: selectedGroups,
          scrollY: window.scrollY,
        } satisfies StoredListState),
      );
    } catch {}
  };

  const stored = readState();
  if (stored) {
    if (searchEl) searchEl.value = stored.search ?? "";

    for (const group of groups) {
      const groupName = group.dataset.filterGroup ?? "";
      const selectedValues = stored.groups?.[groupName] ?? [];
      for (const value of selectedValues) {
        const button = Array.from(
          group.querySelectorAll<HTMLButtonElement>("[data-filter-value]"),
        ).find((candidate) => candidate.dataset.filterValue === value);
        button?.click();
      }
    }

    searchEl?.dispatchEvent(new Event("input", { bubbles: true }));

    const restoreScroll = () => window.scrollTo(0, stored.scrollY ?? 0);
    requestAnimationFrame(() => requestAnimationFrame(restoreScroll));
    window.setTimeout(restoreScroll, 80);
  }

  searchEl?.addEventListener("input", saveState);
  groups.forEach((group) => {
    group.addEventListener("click", (event) => {
      if (
        !(event.target instanceof Element) ||
        !event.target.closest("button")
      ) {
        return;
      }
      queueMicrotask(saveState);
    });
  });
  resetEl?.addEventListener("click", () => queueMicrotask(saveState));
  window.addEventListener("pagehide", saveState);
};
