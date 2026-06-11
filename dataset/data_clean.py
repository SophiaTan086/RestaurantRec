import pandas as pd
import json
import numpy as np
from tqdm import tqdm
import ast

# 读取 Yelp 格式的 JSON 文件
def load_yelp_json(file_path):
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc=f"读取 {file_path}"):
            data.append(json.loads(line))
    return pd.DataFrame(data)

# 读取商家信息
biz = load_yelp_json("yelp_academic_dataset\yelp_academic_dataset_business.json")

food_categories = ['Restaurants', 'Food', 'Cafes', 'Bakeries', 'Desserts', 'Fast Food', 'Coffee & Tea']
biz = biz[biz['categories'].notna()]
biz = biz[biz['categories'].apply(lambda x: any(cat in x for cat in food_categories))]
biz = biz[biz['hours'].notna()] # 只保留有营业时间的商家

def flatten_attributes(attr_dict):
    if not isinstance(attr_dict, dict):
        return {}
    return attr_dict

# 展开属性
attr_df = pd.json_normalize(biz['attributes'].apply(flatten_attributes))
biz = pd.concat([biz.reset_index(drop=True), attr_df.reset_index(drop=True)], axis=1)

# 选择结构化需要的列
biz_clean = biz[[
    'business_id', 'name','address', 'city', 'state','latitude', 'longitude',
    'stars', 'review_count', 'categories', 'hours'
]]

# 重命名 + 清理空值
biz_clean.columns = ['商家ID', '店名', '地址', '城市', '州', '纬度', '经度', '评分', '评论数', '分类', '营业时间']
biz_clean = biz_clean.drop_duplicates(subset=['商家ID'])  # 去重
biz_clean = biz_clean[biz_clean['评分'] >= 1]  # 只保留评分大于等于1的商家
biz_clean = biz_clean[biz_clean['评论数'] >= 100]  # 只保留评论数大于等于100的商家
biz_clean = biz_clean.fillna("未知")  # 填充缺失值

# 随机筛选5000家餐厅数据
biz_clean = biz_clean.sample(n=5000, random_state=42) 
# 保存为结构化 CSV
biz_clean.to_csv("restaurant.csv", index=False, encoding='utf-8-sig')
print("餐厅表完成，共", len(biz_clean), "条有效餐厅数据")



# 读取评论数据
valid_biz_ids = set(biz_clean['商家ID'])
review_clean = []

with open("yelp_academic_dataset\yelp_academic_dataset_review.json", 'r', encoding='utf-8') as f:
    for line in tqdm(f, desc="读取并过滤评论"):
        item = json.loads(line)
        # 只保留目标餐厅的评论，其他直接丢掉！
        if item['business_id'] in valid_biz_ids and item['useful'] >= 10:  # 只保留有用数大于等于10的评论
            review_clean.append({
                '用户ID': item['user_id'],
                '商家ID': item['business_id'],
                '评分': item['stars'],
                '评语': item['text'],
                '评论时间': item['date']
            })

review_clean = pd.DataFrame(review_clean)
review_clean['评论时间'] = pd.to_datetime(review_clean['评论时间'])
review_clean = review_clean[review_clean['评分'] >= 1]
review_clean = review_clean.sort_values(['用户ID', '商家ID', '评论时间'], ascending=[True, True, False])
review_clean = review_clean.drop_duplicates(subset=['用户ID', '商家ID'], keep='first')

review_clean.to_csv("review.csv", index=False, encoding='utf-8-sig')
print("评分表完成，共", len(review_clean), "条有效评分")


# 读取用户数据
user = load_yelp_json("yelp_academic_dataset\yelp_academic_dataset_user.json")

# 保留推荐系统需要的字段
user_clean = user[[
    'user_id', 'name', 'review_count', 'yelping_since', 'average_stars'
]]

user_clean.columns = ['用户ID', '用户名', '用户评论数', '注册时间','用户平均评分']

valid_user_ids = set(review_clean['用户ID'])
user_clean = user_clean[user_clean['用户ID'].isin(valid_user_ids)]
user_clean.to_csv("user.csv", index=False, encoding='utf-8-sig')
print("用户表完成，共", len(user_clean), "位有效用户")