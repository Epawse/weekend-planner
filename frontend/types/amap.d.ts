declare namespace AMap {
  class Map {
    constructor(container: HTMLElement, options?: MapOptions);
    clearMap(): void;
    setFitView(
      overlays?: Overlay[],
      immediately?: boolean,
      avoid?: number[]
    ): void;
    destroy(): void;
  }

  interface MapOptions {
    zoom?: number;
    center?: [number, number] | LngLat;
    mapStyle?: string;
  }

  class LngLat {
    constructor(lng: number, lat: number);
    getLng(): number;
    getLat(): number;
  }

  class Pixel {
    constructor(x: number, y: number);
  }

  class Marker {
    constructor(options?: MarkerOptions);
  }

  interface MarkerOptions {
    position?: [number, number] | LngLat;
    map?: Map;
    label?: {
      content: string;
      offset?: Pixel;
    };
    icon?: string;
  }

  class Polygon {
    constructor(options?: PolygonOptions);
  }

  interface PolygonOptions {
    path?: LngLat[];
    fillColor?: string;
    fillOpacity?: number;
    strokeColor?: string;
    strokeWeight?: number;
    strokeOpacity?: number;
    map?: Map;
  }

  class Polyline {
    constructor(options?: PolylineOptions);
  }

  interface PolylineOptions {
    path?: LngLat[];
    strokeColor?: string;
    strokeWeight?: number;
    strokeOpacity?: number;
    lineJoin?: string;
    lineCap?: string;
    map?: Map;
  }

  type Overlay = Marker | Polygon | Polyline;
}

interface Window {
  AMap: typeof AMap;
}
