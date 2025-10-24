-- 用户每日访问量，以及输入输出Token数量统计明细表
CREATE TABLE "statistics" (
	"uid"	INTEGER,
	"user_name"	TEXT,
	"date"	TEXT,
	"access"	INTEGER,
	"input_token"	INTEGER,
	"output_token"	INTEGER
);