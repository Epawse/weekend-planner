# GIS Tools Integration Research

## Overview

User has GIS professional background. This research covers which GIS capabilities can be integrated as real tools (not mock) to create a strong competitive differentiator.

---

## 1. Isochrone Analysis (等时圈) — "别离家太远"的正确实现

赛题说"别离家太远"→ 不是画个圆（半径搜索），而是"从家出发X分钟内可达的真实区域"。

### Option A: OpenRouteService (推荐 — 免费 + 驾车/步行都支持)

- **免费额度**: 500次/天, 20次/分钟 (云端)
- **支持**: driving-car, foot-walking, cycling-regular
- **输出**: GeoJSON Polygon
- **Python SDK**: `openrouteservice-py`

```python
import openrouteservice as ors

client = ors.Client(key='FREE_API_KEY')

# 从家出发，驾车20/30分钟可达范围
iso = client.isochrones(
    locations=[[116.473168, 39.993015]],  # 北京某小区
    profile='driving-car',
    range_type='time',
    range=[1200, 1800],  # 20分钟, 30分钟 (秒)
)
# 返回 GeoJSON FeatureCollection with Polygon geometries
```

### Option B: 高德地图 ArrivalRange (公交/地铁到达圈)

- 仅支持公交+地铁，不支持驾车
- Web服务API: `/v3/direction/reachcircle`
- 适合"公交可达"场景

### Option C: 高德网格采样法 (驾车等时圈近似)

- 以中心点生成网格 → 批量调用驾车路径规划 → 筛选时间阈值内的点 → 生成凸包
- 消耗大量 API 调用额度，不推荐 hackathon 使用

### 决策: 使用 OpenRouteService

- 免费、支持驾车、Python SDK 成熟
- 500次/天对 Demo 足够（每次规划只需1-2次等时圈调用）
- 输出 GeoJSON 可直接用于前端地图渲染和后端空间过滤

---

## 2. POI 空间过滤 — 等时圈内的餐厅/景点

### 后端: GeoPandas + Shapely (空间连接)

```python
import geopandas as gpd

# 高德 POI 搜索结果 → GeoDataFrame
pois_gdf = gpd.GeoDataFrame(
    pois_df,
    geometry=gpd.points_from_xy(pois_df['lon'], pois_df['lat']),
    crs="EPSG:4326"
)

# OpenRouteService 等时圈 → GeoDataFrame
isochrone_gdf = gpd.GeoDataFrame.from_features(iso['features'], crs="EPSG:4326")

# 空间连接: 只保留等时圈内的 POI
filtered_pois = gpd.sjoin(pois_gdf, isochrone_gdf, how='inner', predicate='within')
```

### 前端: Turf.js (浏览器端轻量空间分析)

```javascript
import * as turf from '@turf/turf';

// 判断 POI 是否在等时圈内
const isInside = turf.booleanPointInPolygon(poiPoint, isochronePolygon);

// 计算两点间直线距离
const distance = turf.distance(point1, point2, { units: 'kilometers' });
```

---

## 3. 多点路径优化 (TSP) — 活动顺序最优化

高德不支持自动途经点排序。需要自己实现 TSP。

### 方案: 简单贪心/2-opt + 高德路径规划验证

```python
from itertools import permutations

def optimize_route(origin, destinations, amap_key):
    """
    对于3-4个途经点，穷举所有排列找最短总时间。
    活动规划场景通常只有3-4个点，穷举可行。
    """
    best_order = None
    best_time = float('inf')
    
    for perm in permutations(destinations):
        total_time = 0
        points = [origin] + list(perm)
        for i in range(len(points) - 1):
            time = get_driving_time(points[i], points[i+1], amap_key)
            total_time += time
        if total_time < best_time:
            best_time = total_time
            best_order = perm
    
    return best_order, best_time
```

对于3-4个活动点，穷举 3!=6 或 4!=24 种排列，每种调用高德路径规划，完全可行。

---

## 4. 地图可视化 — 决赛演示杀手锏

### 推荐: 高德 JS API 2.0 + React (@uiw/react-amap)

**理由**:
- 中国数据质量最好（POI、路网、实时路况）
- 内置 ArrivalRange 插件可直接渲染公交等时圈
- GCJ-02 坐标系原生支持，无需转换
- `@uiw/react-amap` 提供 React 声明式组件

```tsx
import { Map, Polygon, Marker, Polyline } from '@uiw/react-amap';

// 渲染等时圈 + 路线 + POI 标注
<Map zoom={12} center={[116.397, 39.909]}>
  <Polygon path={isochroneCoords} fillColor="#00eeff" fillOpacity={0.2} />
  <Polyline path={routeCoords} strokeColor="#1890ff" strokeWeight={4} />
  {pois.map(poi => <Marker key={poi.id} position={poi.coords} />)}
</Map>
```

### 备选: MapLibre GL JS (如果需要更强的自定义可视化)

- 开源免费，WebGL 渲染
- 更强的 3D/动画能力
- 需要自己处理 GCJ-02 坐标偏移
- 通过 `react-map-gl` 集成 React

### 决策: 高德 JS API 2.0

- 与后端高德 POI/路径规划 API 数据一致（同一坐标系）
- 中国场景数据质量无可替代
- React 集成成熟

---

## 5. 完整 GIS 工具链

```
Agent Tool: get_reachable_area
  → OpenRouteService Isochrone API
  → 返回 GeoJSON Polygon (20/30分钟可达范围)

Agent Tool: search_venues_in_area  
  → 高德 POI 周边搜索 (获取候选 POI)
  → GeoPandas sjoin (过滤等时圈内的 POI)
  → 返回空间过滤后的 POI 列表

Agent Tool: optimize_route
  → TSP 穷举 (3-4个点)
  → 高德驾车路径规划 (验证每段真实时间)
  → 返回最优顺序 + 总时间 + 路线 GeoJSON

Agent Tool: calculate_route
  → 高德路径规划 API
  → 返回距离、时间、路线坐标

Frontend:
  → 高德 JS API 2.0 渲染地图
  → 等时圈多边形 + 路线折线 + POI 标注
  → Turf.js 辅助计算 (距离、面积)
```

---

## 6. 竞争优势分析

| 维度 | 其他团队可能做的 | 我们做的 |
|------|----------------|---------|
| "别离家太远" | 半径3km圆形搜索 | 等时圈分析（考虑路网、拥堵） |
| 活动顺序 | 按时间硬排 | TSP最优路径（最少通勤时间） |
| 路线展示 | 文字描述 | 地图可视化（等时圈+路线+标注） |
| 距离计算 | 直线距离 | 真实驾车/步行时间 |
| 空间约束 | 无 | "步行5分钟内可达下一个活动" |

这些是 GIS 专业背景带来的降维打击——评审一看地图可视化就知道这不是普通的搜索推荐。

---

## 7. API 额度汇总

| 服务 | 免费额度 | 用途 |
|------|---------|------|
| 高德 POI/路径规划 | 10,000次/月 | 搜索+路线 |
| OpenRouteService | 500次/天 | 等时圈 |
| 和风天气 | 50,000次/月 | 天气决策 |

Demo 场景完全够用。
