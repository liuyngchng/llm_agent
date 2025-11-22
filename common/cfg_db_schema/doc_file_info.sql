--文档生成docx文件信息表
CREATE TABLE "docx_file_info" (
	"id"	INTEGER NOT NULL,
	"uid"	INTEGER,
	"task_id"	INTEGER,
	"percent"	INTEGER NOT NULL DEFAULT -1,
	"process_info"	TEXT NOT NULL DEFAULT '已上传，待处理',
	"input_file_path"	TEXT,
	"output_file_path"	TEXT,
	"doc_type"	TEXT,
	"doc_title"	TEXT,
	"keywords"	TEXT,
	"doc_outline"	TEXT,
	"img_count"	INTEGER DEFAULT 0,
	"word_count"	INTEGER DEFAULT 0,
	"vdb_id"	INTEGER,
	"is_include_para_txt"	INTEGER,
	"doc_ctx"	TEXT,
	"vdb_dir"	TEXT,
	"is_para_task_created"	INTEGER NOT NULL DEFAULT 0,
	"create_time"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);