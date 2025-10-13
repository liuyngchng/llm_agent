-- txt2sql用户级提示词模板配置， uid=0 的为公共模板
CREATE TABLE "txt2sql_prompt_template" (
	"id"	INTEGER NOT NULL,
	"name"	TEXT NOT NULL,
	"value"	TEXT NOT NULL,
	"uid"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);