"use client";

import { CircleMarker, MapContainer, Popup, TileLayer, useMapEvents } from "react-leaflet";
import type { MapProps } from "./pilot-map";

const stations = [
  { name: "Ganga at Sangam", latitude: 25.419206, longitude: 81.900522 },
  { name: "Ganga at Rasoolabad", latitude: 25.502474, longitude: 81.855439 },
  { name: "Yamuna at Balua Ghat", latitude: 25.422471, longitude: 81.838806 },
];

function Locate({ onLocate }: Pick<MapProps, "onLocate">) {
  useMapEvents({ click: ({ latlng }) => onLocate?.(latlng.lat, latlng.lng) });
  return null;
}

export default function LeafletMap({ localities, features, onSelect, onLocate, location }: MapProps) {
  const groups = new Map<string, typeof features>();
  for (const feature of features) {
    const key = feature.properties.locality_id;
    groups.set(key, [...(groups.get(key) ?? []), feature]);
  }
  return (
    <MapContainer center={[25.458, 81.865]} zoom={12} scrollWheelZoom={false} className="pilot-map">
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <Locate onLocate={onLocate} />
      {stations.map(({ name, latitude, longitude }) => (
        <CircleMarker key={name} center={[latitude, longitude]} radius={6} color="#286487" fillOpacity={0.85}>
          <Popup><strong>{name}</strong><br />Historical CPCB river station</Popup>
        </CircleMarker>
      ))}
      {localities.filter((item) => !features.some((feature) => feature.properties.locality_id === item.id))
        .map(({ id, name, latitude, longitude }) => (
          <CircleMarker key={id} center={[latitude, longitude]} radius={7} color="#64748b" fillOpacity={0.5}>
            <Popup>{name}<br />Fictional pilot locality</Popup>
          </CircleMarker>
        ))}
      {Array.from(groups.values()).map((group) => {
        if (!group?.length) return null;
        const [lon, lat] = group[0].geometry.coordinates;
        const color = group.some(({ properties }) => properties.id && properties.status !== "RESOLVED")
          ? "#a65e15" : group.some(({ properties }) => properties.id) ? "#127568" : "#64748b";
        return <CircleMarker key={group[0].properties.locality_id} center={[lat, lon]} radius={12}
          color={color} fillOpacity={0.8}>
          <Popup><strong>{group[0].properties.locality}</strong>
            {group.map(({ properties: item }) => <div key={item.id ?? "unverified"}>
              {item.id
                ? <button type="button" onClick={() => onSelect(item.id!)}>{item.category}{item.households ? ` · ${item.households} households` : ""}</button>
                : <span>{item.reports} unverified reports</span>}
            </div>)}
          </Popup>
        </CircleMarker>;
      })}
      {location && <CircleMarker center={location} radius={6} color="#183848" fillOpacity={0.8} />}
    </MapContainer>
  );
}
