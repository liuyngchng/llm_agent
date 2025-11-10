--文档生成各个段落子任务信息表
-- status, 0:表示未完成; 1:表示任务已完成
CREATE TABLE "docx_para_info" (
	"id"	INTEGER NOT NULL,
	"task_id"	INTEGER,
	"para_id"	INTEGER,
	"heading"	TEXT,
	"gen_txt"	TEXT,
	"status"	INTEGER DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);