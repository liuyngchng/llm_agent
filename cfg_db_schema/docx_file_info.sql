--文档生成docx文件信息表
CREATE TABLE "docx_file_info" (
	"id"	INTEGER NOT NULL,
	"file_name"	TEXT,
	"uid"	INTEGER,
	"task_id"	INTEGER,
	"file_path"	TEXT,
	"percent"	INTEGER NOT NULL DEFAULT 0,
	"process_info"	TEXT NOT NULL DEFAULT '已上传，待处理',
	"template_path"	TEXT,
	"doc_type"	TEXT,
	"doc_title"	TEXT,
	"keywords"	TEXT,
	"outline"	TEXT,
	"img_count"	INTEGER DEFAULT 0,
	"create_time"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);