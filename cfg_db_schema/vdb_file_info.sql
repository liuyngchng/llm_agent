--知识库中的文件元数据信息表
CREATE TABLE "vdb_file_info" (
	"id"	INTEGER NOT NULL,
	"name"	TEXT,
	"uid"	INTEGER,
	"vdb_id"	INTEGER,
	"task_id"	INTEGER,
	"file_path"	TEXT,
	"percent"	INTEGER NOT NULL DEFAULT 0,
	"process_info"	TEXT NOT NULL DEFAULT '已上传，待处理',
	"file_md5"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);