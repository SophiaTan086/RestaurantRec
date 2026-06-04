from neo4j import GraphDatabase
from geopy.distance import geodesic

class RestaurantRecommender:
    def __init__(self):
        self.URI = "bolt://localhost:7687"
        self.USER = "neo4j"
        self.PASSWORD = "12345678"
        self.driver = GraphDatabase.driver(self.URI, auth=(self.USER, self.PASSWORD))
        # 屏蔽一些泛标签
        self.black_list = {"Restaurant", "Restaurants", "Food", "Foods", "None", "nan", "Misc", "Other", "Restaurants ", "Food "}

    def close(self):
        self.driver.close()

    # 获取全部餐厅名称
    def get_all_restaurants(self):
        with self.driver.session() as s:
            res = s.run("MATCH (r:Restaurant) WHERE r.name IS NOT NULL RETURN r.name ORDER BY r.name")
            arr = [item["r.name"] for item in res]
        return arr

    # 检索餐厅
    def search_nodes(self, keyword):
        if not keyword.strip():
            return []

        search_kw = keyword.strip().lower()

        # 优化黑名单判断逻辑
        if search_kw in [b.lower() for b in self.black_list]:
            return []

        query = """
        MATCH (r:Restaurant)
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(c:Category)
        WITH r, c
        WHERE toLower(r.name) CONTAINS $kw 
           OR (c IS NOT NULL AND toLower(c.name) CONTAINS $kw)
        
        MATCH (r)-[:BELONGS_TO]->(all_c:Category)
        WITH r, collect(DISTINCT all_c.name) AS category_list
        
        RETURN r.name AS name, 
               r.address AS address, 
               r.rating AS rating, 
               category_list
        ORDER BY r.rating DESC
        """
        
        results = []
        with self.driver.session() as session:
            try:
                res = session.run(query, kw=search_kw)
                for record in res:
                    cats = record["category_list"]
                    # 强行过滤掉
                    cats_clean = [cat.strip() for cat in cats if cat.strip() and cat.strip() not in self.black_list]
                    
                    cuisine_str = ", ".join(cats_clean) if cats_clean else "其他精细菜系"
                    
                    results.append({
                        "餐厅名": record["name"],
                        "地址": record["address"] if record["address"] else "未登记地址",
                        "评分": float(record["rating"]) if record["rating"] else 0.0,
                        "所属菜系": cuisine_str
                    })
            except Exception as e:
                fallback_query = """
                MATCH (r:Restaurant)-[:BELONGS_TO]->(c:Category)
                RETURN r.name AS name, r.address AS address, r.rating AS rating, collect(DISTINCT c.name) AS cats
                """
                res = session.run(fallback_query)
                for record in res:
                    cats = [cat.strip() for cat in record["cats"] if cat.strip() and cat.strip() not in self.black_list]
                    name_match = search_kw in str(record["name"]).lower()
                    cat_match = any(search_kw in cat.lower() for cat in cats)
                    
                    if name_match or cat_match:
                        results.append({
                            "餐厅名": record["name"],
                            "地址": record["address"] if record["address"] else "未登记地址",
                            "评分": float(record["rating"]) if record["rating"] else 0.0,
                            "所属菜系": ", ".join(cats) if cats else "其他精细菜系"
                        })
                results.sort(key=lambda x: -x["评分"])

        return results[:20]

    # 推荐入口
    def recommend_by_rules(self, restaurant_name, strategy):
        if not restaurant_name:
            return []
        if strategy == "同菜系推荐":
            return self._same_category(restaurant_name)
        elif strategy == "喜欢这家的人还喜欢":
            return self._people_like(restaurant_name)
        elif strategy == "距离优先推荐":
            return self._near_rest(restaurant_name)
        return []

    # 同菜系推荐
    def _same_category(self, restaurant_name):
        with self.driver.session() as s:
            sql = """
            MATCH (src:Restaurant{name:$name})-[r1:BELONGS_TO]->(cate:Category)<-[r2:BELONGS_TO]-(rec:Restaurant)
            WHERE src.name <> rec.name AND NOT cate.name IN $black
            
            // 💡 核心修复：按餐厅和地址进行分组，将多个重合的菜系聚合到一个列表里，彻底斩断重复行
            WITH rec, collect(DISTINCT cate.name) AS overlapped_cates
            
            RETURN rec.name AS 餐厅名, 
                   rec.address AS 地址, 
                   rec.rating AS 评分, 
                   apoc.text.join(overlapped_cates, ", ") AS 菜系
            ORDER BY rec.rating DESC 
            LIMIT 8
            """
            try:
                res = s.run(sql, name=restaurant_name, black=list(self.black_list))
                return [dict(i) for i in res]
            except Exception as e:
                #  fallback 兜底方案：如果你的 Neo4j 没有安装 APOC 插件，用纯 Cypher 聚合，并在 Python 层做字符串拼接
                fallback_sql = """
                MATCH (src:Restaurant{name:$name})-[:BELONGS_TO]->(cate:Category)<-[:BELONGS_TO]-(rec:Restaurant)
                WHERE src.name <> rec.name AND NOT cate.name IN $black
                WITH rec, collect(DISTINCT cate.name) AS cates
                RETURN rec.name AS 餐厅名, rec.address AS 地址, rec.rating AS 评分, cates
                ORDER BY rec.rating DESC LIMIT 8
                """
                res = s.run(fallback_sql, name=restaurant_name, black=list(self.black_list))
                arr = []
                for item in res:
                    arr.append({
                        "餐厅名": item["餐厅名"],
                        "地址": item["地址"] if item["地址"] else "未登记地址",
                        "评分": float(item["评分"]) if item["评分"] else 0.0,
                        "菜系": ", ".join(item["cates"])  # 在 Python 中拼装成字符串
                    })
                return arr
    
    # 喜欢这家餐厅的其他人也喜欢
    def _people_like(self, restaurant_name):
        with self.driver.session() as s:
            sql = """
            MATCH (u:User)-[:REVIEWED]->(src:Restaurant{name:$name}), (u)-[:REVIEWED]->(rec:Restaurant)
            WHERE src.name <> rec.name
            RETURN rec.name AS 餐厅名, rec.address AS 地址, rec.rating AS 评分, count(u) AS 相似用户数
            ORDER BY 相似用户数 DESC, rec.rating DESC LIMIT 8
            """
            res = s.run(sql, name=restaurant_name)
            return [dict(i) for i in res]

    # 距离优先
    def _near_rest(self, restaurant_name):
        with self.driver.session() as s:
            pos = s.run("MATCH (r:Restaurant{name:$name}) RETURN r.latitude, r.longitude", name=restaurant_name).single()
            if pos is None:
                return []
            lat, lon = pos["r.latitude"], pos["r.longitude"]
            all_r = s.run("MATCH (r:Restaurant) RETURN r.name, r.address, r.rating, r.latitude, r.longitude")
            arr = []
            for item in all_r:
                if item["r.name"] == restaurant_name:
                    continue
                try:
                    dis = geodesic((lat, lon), (item["r.latitude"], item["r.longitude"])).km
                    arr.append({
                        "餐厅名": item["r.name"],
                        "地址": item["r.address"],
                        "评分": item["r.rating"],
                        "距离(km)": round(dis, 2)
                    })
                except:
                    continue
        arr.sort(key=lambda x: x["距离(km)"])
        return arr[:8]

    # 生成图谱子图
    def fetch_graph_data_by_rest(self, rest_name):
        """
        高阶图谱联动：强行同时提取该餐厅的【精细菜系】以及【真实用户的打分评价关系】
        """
        if not rest_name:
            return []
        results = []
        with self.driver.session() as s:
            sql_cat = """
            MATCH (r:Restaurant{name:$name})-[rel:BELONGS_TO]->(c:Category)
            WHERE NOT c.name IN $black
            RETURN r.name AS src, c.name AS tar, "属于菜系" AS label,"" AS text
            LIMIT 10
            """
            res_cat = s.run(sql_cat, name=rest_name, black=list(self.black_list))
            for r in res_cat:
                if r["src"] and r["tar"]:
                    results.append((r["src"], r["tar"], r["label"],r["text"]))

            sql_user_checked = """
            MATCH (u:User)-[rel:REVIEWED]->(r:Restaurant{name:$name})
            WHERE rel.rating IS NOT NULL
            RETURN COALESCE(u.name, u.id, "用户") AS src, 
                   r.name AS tar, 
                   "打分: " + toString(rel.rating) AS label,
                   COALESCE(rel.text, "该用户仅打分，未填写文字评价。") AS text
            LIMIT 25
            """
            res_user = s.run(sql_user_checked, name=rest_name)
            for r in res_user:
                if r["src"] and r["tar"]:
                    results.append((r["src"], r["tar"], r["label"],r["text"]))
                    
        return results