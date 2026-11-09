"""Build lightweight globe and Korea geometry for the startup animation."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/brand/ne_110m_land.geojson'
ASSETS = ROOT / 'view/assets'


def inside(point, ring):
    x, y = point
    result = False
    a = ring[-1]
    for b in ring:
        if (a[1] > y) != (b[1] > y):
            if x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                result = not result
        a = b
    return result


def simplify(points, tolerance=.12):
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = dx*dx+dy*dy
    distances = []
    for p in points[1:-1]:
        t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length)) if length else 0
        distances.append(math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy))
    farthest = max(distances)
    if farthest <= tolerance:
        return [a, b]
    i = distances.index(farthest)+1
    return simplify(points[:i+1], tolerance)[:-1]+simplify(points[i:], tolerance)


def nearest_edges(points, limit, count=3):
    edges = set()
    for i, a in enumerate(points):
        neighbors = sorted((sum((x-y)**2 for x, y in zip(a, b)), j)
                           for j, b in enumerate(points) if i != j)[:count]
        for distance, j in neighbors:
            if distance < limit*limit:
                edges.add(tuple(sorted((i, j))))
    return sorted(edges)


def build():
    land = json.loads(SOURCE.read_text(encoding='utf-8'))
    polygons = []
    for feature in land['features']:
        geometry = feature['geometry']
        ringsets = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        for rings in ringsets:
            xs, ys = zip(*rings[0])
            polygons.append((min(xs), min(ys), max(xs), max(ys), rings))
    points = []
    for i in range(67):
        lat = -81+i*2.6
        step = 2.6/max(.12, math.cos(math.radians(lat)))
        lon = -180+(i % 2)*step/2
        while lon < 180:
            if any(left <= lon <= right and bottom <= lat <= top and inside((lon, lat), rings[0])
                   and not any(inside((lon, lat), hole) for hole in rings[1:])
                   for left, bottom, right, top, rings in polygons):
                points.append([round(lon, 3), round(lat, 3)])
            lon += step
    vectors = []
    for lon, lat in points:
        lon, lat = math.radians(lon), math.radians(lat)
        vectors.append((math.cos(lat)*math.sin(lon), math.sin(lat), math.cos(lat)*math.cos(lon)))
    brand = json.loads((ASSETS/'brand-population.json').read_text(encoding='utf-8'))
    korea = [[p['x'], p['y'], p['lon'], p['lat'],
              round(min(1, math.log1p(max(0, p['density']))/math.log1p(5000)), 3)] for p in brand['points']]
    result = {
        'world': {'points': points, 'edges': nearest_edges(vectors, .075, 3)},
        'korea': {'points': korea, 'edges': nearest_edges([p[:2] for p in korea], 3.5, 3),
                  'outlines': [[simplify(ring) for ring in polygon] for polygon in brand['outlines']]},
        'sources': {
            'world': {'name': 'Natural Earth 1:110m land', 'license': 'Public domain',
                      'url': 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson',
                      'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()},
            'korea': {'data': 'brand-population.json', 'license': 'CC BY 4.0',
                      'attribution': brand['attribution'], 'doi': brand['doi']},
            'appearance': 'World nodes are decorative, not population measurements. Korea uses the brand population aggregation.'}}
    target = ASSETS/'intro-geometry.json'
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(f'{len(points)} globe nodes, {len(korea)} Korea nodes, {target.stat().st_size:,} bytes')


if __name__ == '__main__':
    build()
