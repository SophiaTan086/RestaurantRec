```
RESTAURANTREC-MAIN/
├── dataset/
│   ├── restaurant.csv         # 餐厅基本信息数据集
│   ├── user.csv               # 用户基本信息数据集
│   ├── review.csv             # 用户评语数据集
├── build_kg.py                # 构建知识图谱
├── recommender.py             # 核心推荐算法
├── app.py                     # 交互前端       
└── requirements.txt           # 依赖列表
```
使用方法是：先打开Neo4j，启动任意空数据库显示running，然后配置依赖文件 pip install -r requirements.txt，接着先运行python build_kg.py，再运行python app.py，最后打开提示显示的网站就可以使用了，网站的具体使用方法在每个页面均有标注。
