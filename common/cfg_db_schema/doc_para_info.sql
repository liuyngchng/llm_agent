--文档生成各个段落子任务信息表
-- status, 0:表示未完成; 1:表示任务已完成
CREATE TABLE "doc_para_info" (
	"id"	INTEGER NOT NULL,
	"uid"	INTEGER NOT NULL,
	"task_id"	INTEGER NOT NULL,
	"para_id"	INTEGER NOT NULL,
	"heading"	TEXT,
	"gen_txt"	TEXT,
	"status"	INTEGER DEFAULT 0,
	"unique_key"	TEXT,
	"para_text"	TEXT,
	"user_comment"	TEXT,
	"current_sub_title"	TEXT,
	"namespaces"	TEXT,
	"contains_mermaid"	INTEGER NOT NULL DEFAULT 0,
	"word_count"	INTEGER NOT NULL DEFAULT 0,
	"create_time"	TEXT NOT NULL,
	"update_time"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);