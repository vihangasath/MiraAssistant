// Published tours shown on the landing grid. Mirrors ceylon-compass-dataset/content/tours (status: published).
// No prices here: the pages' "from" prices are not from the rate workbook and disagree with it, so a price
// only ever comes from a quote in the chat.
// The stale "Winter 2023/24 early bird" page and the draft Northern tour are left out on purpose.
export interface TourTeaser {
  title: string;
  category: string;
  group: "day" | "round" | "stay" | "special";
  duration: string;
  places: string;
  art?: string; // destination illustration, when the first place is not the best picture
}

export const TOURS: TourTeaser[] = [
  { title: "Sigiriya and Minneriya Day Tour from Kandy", category: "Day tour", group: "day", duration: "1 day", places: "Sigiriya · Minneriya" },
  { title: "Whale and Dolphin Watching Tour in Mirissa", category: "Day tour", group: "day", duration: "1 day", places: "Mirissa" },
  { title: "Train and Day Tour from Kandy to Nuwara Eliya", category: "Day tour", group: "day", duration: "2 days", places: "Kandy · Nuwara Eliya", art: "nuwara-eliya" },
  { title: "Kandy City Tour", category: "City tour", group: "day", duration: "1 day", places: "Kandy" },
  { title: "Colombo City Tour", category: "City tour", group: "day", duration: "1 day", places: "Colombo" },
  { title: "Galle Fort Walking Tour", category: "City tour", group: "day", duration: "Half day", places: "Galle" },
  { title: "Highlights of Sri Lanka", category: "Round trip", group: "round", duration: "8 days", places: "Sigiriya · Kandy · Galle" },
  { title: "Cultural Triangle Sri Lanka Package", category: "Round trip", group: "round", duration: "7 days", places: "Anuradhapura · Sigiriya · Kandy" },
  { title: "Cultural Triangle Tour", category: "Round trip", group: "round", duration: "6 days", places: "Sigiriya · Polonnaruwa · Kandy", art: "polonnaruwa" },
  { title: "Treasures of Sri Lanka", category: "Round trip", group: "round", duration: "14 days", places: "Anuradhapura · Ella · Yala · Galle", art: "galle" },
  { title: "Instafamous Sri Lanka", category: "Round trip", group: "round", duration: "11 days", places: "Sigiriya · Ella · Mirissa", art: "ella" },
  { title: "Sri Lanka Beach Stay – Mirissa", category: "Beach stay", group: "stay", duration: "7 days", places: "Mirissa" },
  { title: "Kandy Heritage Stay", category: "Short stay", group: "stay", duration: "3 days", places: "Kandy" },
  { title: "Wildlife Photography Tour", category: "Special interest", group: "special", duration: "7 days", places: "Udawalawe · Yala", art: "yala" },
];

export const TOUR_FILTERS = [
  { id: "all", label: "For you" },
  { id: "day", label: "Day tours" },
  { id: "round", label: "Round trips" },
  { id: "stay", label: "Stays" },
  { id: "special", label: "Wildlife" },
] as const;
