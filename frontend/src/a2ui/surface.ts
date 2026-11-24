// A small A2UI v0.9 message processor for Mira's catalog.
// The server already validates every payload; this is a second check so an unknown
// component or a literal price can never render.
import type { A2uiMessage } from "../agui";

export const CATALOG_ID = "https://ceyloncompass.example/a2ui/catalogs/mira/v1.json";
export const KNOWN_COMPONENTS = new Set([
  "Column", "Text", "QuickReplies", "TravellerPicker", "TourCard", "ItineraryDay", "PriceBreakdown",
  "SpecialistHandoff", "BookingForm", "EnquiryForm", "SourceList", "Notice",
]);

export interface ComponentNode {
  id: string;
  component: string;
  [prop: string]: any;
}

export interface Surface {
  id: string;
  catalogId: string;
  components: Map<string, ComponentNode>;
  data: Record<string, any>;
  rejected: string[];
}

function setPath(target: Record<string, any>, path: string, value: unknown) {
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) {
    Object.assign(target, value);
    return;
  }
  let cur = target;
  for (const p of parts.slice(0, -1)) cur = cur[p] ??= {};
  cur[parts[parts.length - 1]] = value;
}

export function resolve(surface: Surface, value: any): any {
  if (value && typeof value === "object" && typeof value.path === "string" && Object.keys(value).length === 1) {
    return value.path.split("/").filter(Boolean).reduce((acc: any, k: string) => (acc == null ? undefined : acc[k]), surface.data);
  }
  return value;
}

export function processMessages(messages: A2uiMessage[]): Surface | null {
  let surface: Surface | null = null;
  for (const msg of messages) {
    if (msg.version !== "v0.9") continue;
    if (msg.createSurface) {
      if (msg.createSurface.catalogId !== CATALOG_ID) return null;
      surface = { id: msg.createSurface.surfaceId, catalogId: CATALOG_ID, components: new Map(), data: {}, rejected: [] };
    } else if (surface && msg.updateDataModel && msg.updateDataModel.surfaceId === surface.id) {
      setPath(surface.data, msg.updateDataModel.path, msg.updateDataModel.value);
    } else if (surface && msg.updateComponents && msg.updateComponents.surfaceId === surface.id) {
      for (const c of msg.updateComponents.components as ComponentNode[]) {
        if (!KNOWN_COMPONENTS.has(c.component)) {
          surface.rejected.push(c.component);
          continue;
        }
        surface.components.set(c.id, c);
      }
    }
  }
  return surface;
}
