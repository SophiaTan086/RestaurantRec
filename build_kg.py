#数据库实例建立：选用版本：5.26.19
import pandas as pd
from neo4j import GraphDatabase

# ----------------------
# Neo4j 连接信息
# ----------------------
URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "12345678"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# ----------------------
# 读取 CSV
# ----------------------
restaurant_df = pd.read_csv("dataset/restaurant.csv")
user_df = pd.read_csv("dataset/user.csv")
review_df = pd.read_csv("dataset/review.csv")

# ----------------------
# 节点创建
# ----------------------
def create_restaurant(tx, row):
    tx.run("""
        MERGE (r:Restaurant {id:$id})
        SET r.name=$name,
            r.address=$address,
            r.latitude=$latitude,
            r.longitude=$longitude,
            r.rating=$rating,
            r.review_count=$review_count,
            r.hours=$hours
    """,
    id=row["商家ID"],
    name=row["店名"],
    address=row["地址"],
    latitude=row["纬度"],
    longitude=row["经度"],
    rating=row["评分"],
    review_count=row["评论数"],
    hours=row["营业时间"]
    )

def create_user(tx, row):
    tx.run("""
        MERGE (u:User {id:$id})
        SET u.username=$username,
            u.review_count=$review_count,
            u.join_date=$join_date,
            u.avg_rating=$avg_rating
    """,
    id=row["用户ID"],
    username=row["用户名"],
    review_count=row["用户评论数"],
    join_date=row["注册时间"],
    avg_rating=row["用户平均评分"]
    )

def create_review_relation(tx, row):
    tx.run("""
        MATCH (u:User {id:$user_id}), (r:Restaurant {id:$restaurant_id})
        MERGE (u)-[rel:REVIEWED]->(r)
        SET rel.rating=$rating, 
            rel.text=$text,
            rel.review_time=$review_time
    """,
    user_id=row["用户ID"],
    restaurant_id=row["商家ID"],
    rating=row["评分"],
    text=row["评语"],
    review_time=row["评论时间"]
    )

# ----------------------
# 分类 / 城市 / 州 / 国家节点 + 关系
# ----------------------
def create_category(tx, name):
    tx.run("MERGE (c:Category {name:$name})", name=name)

def create_city(tx, name):
    tx.run("MERGE (c:City {name:$name})", name=name)

def create_state(tx, name):
    tx.run("MERGE (s:State {name:$name})", name=name)

def create_country(tx, name):
    tx.run("MERGE (c:Country {name:$name})", name=name)

def create_belongs_to(tx, restaurant_id, category_name):
    tx.run("""
        MATCH (r:Restaurant {id:$restaurant_id}), (c:Category {name:$category_name})
        MERGE (r)-[:BELONGS_TO]->(c)
    """, restaurant_id=restaurant_id, category_name=category_name)

def create_located_in(tx, restaurant_id, city_name):
    tx.run("""
        MATCH (r:Restaurant {id:$restaurant_id}), (c:City {name:$city_name})
        MERGE (r)-[:LOCATED_IN]->(c)
    """, restaurant_id=restaurant_id, city_name=city_name)

def create_in_state(tx, city_name, state_name):
    tx.run("""
        MATCH (c:City {name:$city_name}), (s:State {name:$state_name})
        MERGE (c)-[:IN_STATE]->(s)
    """, city_name=city_name, state_name=state_name)

def create_in_country(tx, state_name, country_name):
    tx.run("""
        MATCH (s:State {name:$state_name}), (c:Country {name:$country_name})
        MERGE (s)-[:IN_COUNTRY]->(c)
    """, state_name=state_name, country_name=country_name)

# ----------------------
# 用户画像：User -> LIKES -> Category
# ----------------------
def create_user_likes(tx, user_id, category_name):
    tx.run("""
        MATCH (u:User {id:$user_id}), (c:Category {name:$category_name})
        MERGE (u)-[:LIKES]->(c)
    """, user_id=user_id, category_name=category_name)

# ----------------------
# 批量构建
# ----------------------
with driver.session() as session:

    # 1. Restaurant
    print("创建Restaurant节点...")
    for _, row in restaurant_df.iterrows():
        session.execute_write(create_restaurant, row)

    # 2. User
    print("创建User节点...")
    for _, row in user_df.iterrows():
        session.execute_write(create_user, row)

    # 3. REVIEWED关系
    print("创建REVIEWED关系...")
    for _, row in review_df.iterrows():
        session.execute_write(create_review_relation, row)

    # 4. Category + BELONGS_TO
    print("创建Category节点和BELONGS_TO关系...")
    for _, row in restaurant_df.iterrows():
        categories = str(row["分类"]).split(",")
        for cat in categories:
            cat = cat.strip()
            if cat:
                session.execute_write(create_category, cat)
                session.execute_write(create_belongs_to, row["商家ID"], cat)

    # 5. City + LOCATED_IN
    print("创建City节点和LOCATED_IN关系...")
    for _, row in restaurant_df.iterrows():
        city = str(row["城市"]).strip()
        if city:
            session.execute_write(create_city, city)
            session.execute_write(create_located_in, row["商家ID"], city)

    # 6. State + IN_STATE
    print("创建State节点和IN_STATE关系...")
    for _, row in restaurant_df.iterrows():
        state = str(row["州"]).strip()
        city = str(row["城市"]).strip()
        if state and city:
            session.execute_write(create_state, state)
            session.execute_write(create_in_state, city, state)

    # 7. Country + IN_COUNTRY
    print("创建Country节点和IN_COUNTRY关系...")
    country_name = "United States"
    session.execute_write(create_country, country_name)
    states = restaurant_df["州"].dropna().unique()
    for state in states:
        session.execute_write(create_in_country, state, country_name)

    # 8. 用户画像：计算每个用户喜欢的分类
    print("创建用户画像 LIKES 关系...")
    # 按用户ID统计评论过的餐厅所属分类
    user_categories = {}
    for _, row in review_df.iterrows():
        user_id = row["用户ID"]
        restaurant_id = row["商家ID"]
        categories = restaurant_df.loc[restaurant_df["商家ID"]==restaurant_id, "分类"].values
        if len(categories) > 0:
            cats = str(categories[0]).split(",")
            if user_id not in user_categories:
                user_categories[user_id] = set()
            for cat in cats:
                cat = cat.strip()
                if cat:
                    user_categories[user_id].add(cat)
    # 创建关系
    for user_id, cats in user_categories.items():
        for cat in cats:
            session.execute_write(create_user_likes, user_id, cat)

    # 9. 建索引和唯一约束
    print("创建索引和唯一约束...")
    session.execute_write(lambda tx: tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Restaurant) REQUIRE r.id IS UNIQUE"))
    session.execute_write(lambda tx: tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"))
    session.execute_write(lambda tx: tx.run("CREATE INDEX IF NOT EXISTS FOR (c:Category) ON (c.name)"))
    session.execute_write(lambda tx: tx.run("CREATE INDEX IF NOT EXISTS FOR (c:City) ON (c.name)"))
    session.execute_write(lambda tx: tx.run("CREATE INDEX IF NOT EXISTS FOR (s:State) ON (s.name)"))
    session.execute_write(lambda tx: tx.run("CREATE INDEX IF NOT EXISTS FOR (c:Country) ON (c.name)"))

print("知识图谱构建完成！")
