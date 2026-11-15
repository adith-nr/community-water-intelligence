"use client";

import dynamic from "next/dynamic";

export type Locality = { id: string; name: string; city: string; latitude: number; longitude: number };
export type MapFeature = {
  geometry: { coordinates: [number, number] };
  properties: {
    id?: string; locality_id: string; locality: string; status: string;
    category?: string; households?: number; reports?: number;
  };
};
export type MapProps = {
  localities: Locality[];
  features: MapFeature[];
  onSelect: (id: string) => void;
  onLocate?: (lat: number, lon: number) => void;
  location?: [number, number];
};

const Map = dynamic(() => import("./leaflet-map"), {
  ssr: false,
  loading: () => <p role="status" className="p-5">Loading map…</p>,
});

export default function PilotMap(props: MapProps) {
  return <Map {...props} />;
}
