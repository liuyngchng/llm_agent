# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

"""
# setup vector db library
pip install -U pymilvus
# setup embedding models library in milvus style, if you do not want to use it, ignore this step
pip install "pymilvus[model]"
"""

from pymilvus import MilvusClient, FieldSchema, DataType, CollectionSchema
from pymilvus import model
from pymilvus.milvus_client import IndexParams
from sentence_transformers import SentenceTransformer
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

embedding_model = "../bge-large-zh-v1.5"

my_collection_name = "demo_collection"


if __name__=="__main__":
    # init milvus client
    local_model = SentenceTransformer(embedding_model)
    # init a milvus client from local file, local file will be created automatically if not exist
    # client = MilvusClient("milvus_demo.db")
    # init a milvus client from a remote milvus host with or without authentication
    client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
    if client.has_collection(collection_name=my_collection_name):
        client.drop_collection(collection_name=my_collection_name)
    # 使用默认的 schema
    # client.create_collection(
    #     collection_name=my_collection_name,
    #     dimension=1024,  # The vectors we will use in this demo has 1024 dimensions
    # )

    # 使用自定义的 schema
    # Create a collection using the user-defined schema
    primary_key = FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
    )

    vector = FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=1024,
    )
    text_field = FieldSchema(
        name="text",
        dtype=DataType.VARCHAR,
        max_length=500  # VARCHAR 类型必须指定最大长度
    )

    subject_field = FieldSchema(
        name="subject",
        dtype=DataType.VARCHAR,
        max_length=100
    )

    customized_schema = CollectionSchema(
        fields=[primary_key, vector, text_field, subject_field]  # 包含所有字段
    )
    client.create_collection(
        collection_name=my_collection_name,schema=customized_schema
    )

    # milvus官方文档做法， 默认会从 Hugging Face 下载模型 GPTCache/paraphrase-albert-small-v2
    # embedding_fn = model.DefaultEmbeddingFunction()

    docs = [
        "Artificial intelligence was founded as an academic discipline in 1956.",
        "Alan Turing was the first person to conduct substantial research in AI.",
        "Born in Maida Vale, London, Turing was raised in southern England.",
    ]

    # txt do vector data
    # milvus官方文档做法
    # vectors = embedding_fn.encode_documents(docs)
    # print("Dim:", embedding_fn.dim, vectors[0].shape)  # Dim: 768 (768,)
    # vector data
    vectors = [local_model.encode(doc).tolist() for doc in docs]
    logger.info(f"dimension:, {local_model.get_sentence_embedding_dimension()}, {len(vectors[0])}")
    # build data which will be saved in db
    data = [
        {"id": i, "vector": vectors[i], "text": docs[i], "subject": "history"}
        for i in range(len(vectors))
    ]
    logger.info(f"data has, {len(data)} entities, each with fields:{data[0].keys()}")
    logger.info(f"vector dimension: {len(data[0]["vector"])}")

    # insert vector data into db file
    res = client.insert(collection_name=my_collection_name, data=data)
    logger.info(f"insert data result :{res}")

    # 创建向量索引
    index_params = IndexParams()
    index_params.add_index(
        field_name="vector",  # 指定向量字段名
        index_type="IVF_FLAT",  # 索引类型
        index_name="my_index",  # 可以自定义索引名称，也可以留空由系统生成
        metric_type="IP",  # 度量类型
        params={"nlist": 128}  # 索引参数
    )
    client.create_index(
        collection_name=my_collection_name,
        index_params=index_params
    )
    # 加载集合到内存
    client.load_collection(collection_name=my_collection_name)

    # semantic search
    # vector search
    vector_search_condition= "Who is Alan Turing?"
    query_vectors = local_model.encode([vector_search_condition]).tolist()
    # If you don't have the embedding function you can use a fake vector to finish the demo:
    # query_vectors = [ [ random.uniform(-1, 1) for _ in range(768) ] ]

    res = client.search(
        collection_name=my_collection_name,  # target collection
        data=query_vectors,  # query vectors
        limit=2,  # number of returned entities
        output_fields=["text", "subject"],  # specifies fields to be returned
    )
    logger.info(f"vector search result, {res}, search condition, {vector_search_condition}")

    # Vector Search with Metadata Filtering
    # Insert more docs in another subject.
    docs = [
        "Machine learning has been used for drug design.",
        "Computational synthesis with AI algorithms predicts molecular properties.",
        "DDR1 is involved in cancers and fibrosis.",
    ]
    vectors = [local_model.encode(doc).tolist() for doc in docs]
    data = [
        {"id": 3 + i, "vector": vectors[i], "text": docs[i], "subject": "biology"}
        for i in range(len(vectors))
    ]

    client.insert(collection_name=my_collection_name, data=data)

    # This will exclude any text in "history" subject despite close to the query vector.
    search_condition = "tell me AI related information"
    filter_condition = "subject == 'history'"
    res = client.search(
        collection_name=my_collection_name,
        data=local_model.encode([search_condition]).tolist(),
        filter=filter_condition,
        limit=2,
        output_fields=["text", "subject"],
    )
    logger.info(f"vector search with metadata filtering {res}, "
                f"search_condition, {search_condition}, filter_condition, {filter_condition}")

    # delete entities
    client.delete(
        collection_name=my_collection_name,
        ids=[3, 6, 7]
    )
    # {'delete_count': 3}
    client.delete(
        collection_name=my_collection_name,
        filter="id in [1, 8, 9] and subject like 'b%'"
    )

    # upsert
    upsert_data = [
        {"id": 3 + i, "vector": vectors[i], "text": docs[i], "subject": "biology"}
        for i in range(len(vectors))
    ]
    res = client.upsert(
        collection_name=my_collection_name,
        data=upsert_data
    )

    # close the client after all work done
    client.close()
