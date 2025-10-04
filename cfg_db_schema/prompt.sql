--提示词配置
CREATE TABLE "prompt" (
	"id"	INTEGER NOT NULL UNIQUE,
	"uid"	INTEGER,
	"name"	TEXT,
	"value"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);