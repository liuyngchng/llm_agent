--文档生成各个段落子任务信息表
-- status, 0:表示未完成; 1:表示任务已完成
CREATE TABLE "docx_para_info" (
	"id"	INTEGER NOT NULL,
	"uid"	INTEGER NOT NULL,
	"task_id"	INTEGER NOT NULL,
	"para_id"	INTEGER NOT NULL,
	"heading"	TEXT,
	"gen_txt"	TEXT,
	"status"	INTEGER DEFAULT 0,
	"unique_key"	TEXT,
	"paragraph_prompt"	TEXT,
	"user_comment"	TEXT,
	"current_sub_title"	TEXT,
	"namespaces"	TEXT,
	"create_time"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);