--数据查询数据源配置表
CREATE TABLE "db_config" (
	"uid"	INTEGER NOT NULL,
	"db_type"	TEXT,
	"db_host"	TEXT,
	"db_port"	NUMERIC,
	"db_name"	TEXT,
	"db_usr"	TEXT,
	"db_psw"	TEXT,
	"tables"	TEXT DEFAULT ' ',
	"add_chart"	INTEGER NOT NULL DEFAULT 0,
	"is_strict"	INTEGER NOT NULL DEFAULT 0,
	"llm_ctx"	TEXT,
	PRIMARY KEY("uid")
);