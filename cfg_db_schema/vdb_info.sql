--知识库向量数据库元数据信息表
CREATE TABLE "vdb_info" (
	"id"	INTEGER NOT NULL UNIQUE,
	"name"	INTEGER,
	"uid"	INTEGER,
	"is_public"	INTEGER,
	"is_default"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);