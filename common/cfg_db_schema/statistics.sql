-- 用户每日访问量，以及输入输出Token数量统计明细表
CREATE TABLE "statistics" (
	"id"	INTEGER NOT NULL UNIQUE,
	"uid"	INTEGER NOT NULL,
	"nickname"	TEXT NOT NULL,
	"date"	TEXT NOT NULL,
	"access_count"	INTEGER NOT NULL DEFAULT 0,
	"input_token"	INTEGER NOT NULL DEFAULT 0,
	"output_token"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);