"""Render the brand mark from a saved WorldPop population-density aggregation.

Default: Python standard library only. --aggregate additionally uses Pillow and
NumPy to read the source GeoTIFFs in .cache/brand (URLs recorded in the output).
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache/brand"
ASSETS = ROOT / "view/assets"
KM_PER_DEGREE = math.pi * 6371.0088 / 180
COS_LAT = math.cos(math.radians(38))
BIN_KM = 20


def project(lon, lat):
    return lon * COS_LAT * KM_PER_DEGREE, -lat * KM_PER_DEGREE


def aggregate():
    import numpy as np
    from PIL import Image, ImageDraw

    countries = []
    polygons = []
    for iso in ("kor", "prk"):
        info = json.loads((CACHE / f"{iso}-boundary.json").read_text(encoding="utf-8"))
        countries.append((iso, info))
        polygons.extend(info["geometry"]["coordinates"])
    extent = [project(*point) for polygon in polygons for ring in polygon for point in ring]
    left, right = min(p[0] for p in extent), max(p[0] for p in extent)
    top, bottom = min(p[1] for p in extent), max(p[1] for p in extent)
    columns = math.ceil((right-left)/BIN_KM)+1
    rows = math.ceil((bottom-top)/BIN_KM)+1
    size = columns*rows
    population, area, sum_x, sum_y = [np.zeros(size, dtype=np.float64) for _ in range(4)]
    sources = []
    for iso, info in countries:
        path = CACHE / f"{iso}-population-2020.tif"
        image = Image.open(path)
        values = np.asarray(image, dtype=np.float64)
        dx, dy, _ = image.tag_v2[33550]
        _, _, _, west, north, _ = image.tag_v2[33922]
        mask_image = Image.new("1", image.size)
        draw = ImageDraw.Draw(mask_image)
        for polygon in info["geometry"]["coordinates"]:
            for index, ring in enumerate(polygon):
                pixels = [((lon-west)/dx, (north-lat)/dy) for lon, lat in ring]
                draw.polygon(pixels, fill=1 if index == 0 else 0)
        # The constrained raster may have nodata on uninhabited land. Include
        # that land in the denominator, using the country boundary as its mask.
        land = np.asarray(mask_image) | (values >= 0)
        iy, ix = np.nonzero(land)
        lon = west+(ix+.5)*dx
        lat = north-(iy+.5)*dy
        x, y = lon*COS_LAT*KM_PER_DEGREE, -lat*KM_PER_DEGREE
        bx = np.clip(((x-left)/BIN_KM).astype(int), 0, columns-1)
        by = np.clip(((y-top)/BIN_KM).astype(int), 0, rows-1)
        key = by*columns+bx
        cell_area = (6371.0088**2 * math.radians(dx) *
                     (np.sin(np.radians(lat+dy/2))-np.sin(np.radians(lat-dy/2))))
        people = np.maximum(values[iy, ix], 0)
        population += np.bincount(key, weights=people, minlength=size)
        area += np.bincount(key, weights=cell_area, minlength=size)
        sum_x += np.bincount(key, weights=x*cell_area, minlength=size)
        sum_y += np.bincount(key, weights=y*cell_area, minlength=size)
        files = json.loads((CACHE / f"{iso}-files.json").read_text(encoding="utf-8"))
        sources.append({"country":iso.upper(), "url":files["population"]["1km"],
                        "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                        "boundaryUrl":f"https://api.worldpop.org/v3/countries/{iso.upper()}?year=2020&geometry=true",
                        "boundarySha256":hashlib.sha256((CACHE/f"{iso}-boundary.json").read_bytes()).hexdigest(),
                        "populationSum":round(float(people.sum()),2)})
    scale = min(80/(right-left),112/(bottom-top))
    offset_x = (96-(right-left)*scale)/2
    offset_y = (128-(bottom-top)*scale)/2

    def screen(x, y):
        return round(offset_x+(x-left)*scale,3), round(offset_y+(y-top)*scale,3)

    points = []
    for i in range(size):
        if area[i] < 3:
            continue
        x, y = sum_x[i]/area[i], sum_y[i]/area[i]
        sx, sy = screen(x, y)
        points.append({"x":sx,"y":sy,"lon":round(x/(COS_LAT*KM_PER_DEGREE),5),
                       "lat":round(-y/KM_PER_DEGREE,5),"population":round(float(population[i]),2),
                       "landKm2":round(float(area[i]),3),
                       "density":round(float(population[i]/area[i]),3)})
    outlines = [[[screen(*project(*point)) for point in ring] for ring in polygon] for polygon in polygons]
    data = {"dataset":"WorldPop Global2 R2025A v1, UN-adjusted 1km population estimates",
            "year":2020,"sourcePage":"https://api.worldpop.org/v3/about",
            "attribution":"WorldPop, University of Southampton; Bondarenko et al. (2025)",
            "doi":"https://doi.org/10.5258/SOTON/WP00840",
            "license":"CC BY 4.0","licenseUrl":"https://creativecommons.org/licenses/by/4.0/",
            "method":{"binKm":BIN_KM,"density":"People per km² of land in each projected 20km bin",
                      "projection":"Equirectangular, standard parallel 38°N",
                      "position":"Land-area centroid of source cells in each bin",
                      "tone":"min(1, log1p(density) / log1p(5000))",
                      "smallIslands":"Bins with less than 3km² of land omitted at icon scale",
                      "edges":"Short decorative connections; not migration or transport data"},
            "sources":sources,"outlines":outlines,"points":points}
    (ASSETS/"brand-population.json").write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    return data


def tone(density):
    return min(1, math.log1p(max(0, density))/math.log1p(5000))


def render(data):
    points = data["points"]
    data["method"]["appearance"] = {
        "radius": "0.50 + 0.40 * tone^1.1",
        "opacity": "0.58 + 0.24 * tone",
        "color": "linear RGB interpolation from #75a28d to #b7dac2",
    }
    (ASSETS/"brand-population.json").write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 128" fill="none">',
           '<title>이직·실업급여 온톨로지</title>',
           '<desc>2020년 인구 밀도를 노드의 크기와 밝기로 표현한 한반도. WorldPop, University of Southampton, CC BY 4.0. 원본 1km 인구 추정치를 20km 구간으로 합산하고 명암을 로그 변환함.</desc>',
           '<metadata>WorldPop Global2 R2025A v1; Bondarenko et al. (2025); https://doi.org/10.5258/SOTON/WP00840 ; https://creativecommons.org/licenses/by/4.0/ ; aggregation: brand-population.json</metadata>',
           '<g fill="#84bca6" opacity=".08" fill-rule="evenodd">']
    for polygon in data["outlines"]:
        path = "".join("M"+"L".join(f"{x:.2f},{y:.2f}" for x,y in ring)+"Z" for ring in polygon)
        svg.append(f'<path d="{path}"/>')
    svg.append('</g><g stroke="#80b79e" stroke-width=".3">')
    edge_paths = {}
    for i,p in enumerate(points):
        near = sorted((math.hypot(p["x"]-q["x"],p["y"]-q["y"]),j) for j,q in enumerate(points[:i]))[:3]
        for distance,j in near:
            if distance>3.5:
                continue
            q=points[j]
            opacity=.16+.08*(tone(p["density"])+tone(q["density"]))/2
            edge_paths.setdefault(round(opacity,2),[]).append(f'M{p["x"]:.2f} {p["y"]:.2f} {q["x"]:.2f} {q["y"]:.2f}')
    for opacity, segments in edge_paths.items():
        svg.append(f'<path d="{"".join(segments)}" opacity="{opacity:.2f}"/>')
    svg.append('</g><g>')
    for p in points:
        t=tone(p["density"])
        radius=.50+.40*t**1.1
        opacity=.58+.24*t
        color="#"+"".join(f"{round(a+(b-a)*t):02x}" for a,b in zip((117,162,141),(183,218,194)))
        svg.append(f'<circle cx="{p["x"]:.2f}" cy="{p["y"]:.2f}" r="{radius:.2f}" fill="{color}" opacity="{opacity:.2f}"/>')
    svg.append('</g></svg>')
    (ASSETS/"brand-mark.svg").write_text("\n".join(svg)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate",action="store_true")
    args=parser.parse_args()
    data=aggregate() if args.aggregate else json.loads((ASSETS/"brand-population.json").read_text(encoding="utf-8"))
    render(data)
    print(f"Rendered {len(data['points'])} population-density nodes ({data['year']}).")
