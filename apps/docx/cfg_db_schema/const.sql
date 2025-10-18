--常量配置信息表
CREATE TABLE "const" (
	"key"	TEXT NOT NULL,
	"value"	TEXT NOT NULL,
	"app"	TEXT NOT NULL,
	PRIMARY KEY("key","app")
);