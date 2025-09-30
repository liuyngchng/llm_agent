--缓存信息表
CREATE TABLE "cache_info" (
	"key"	TEXT NOT NULL UNIQUE,
	"value"	TEXT NOT NULL,
	"timestamp"	TEXT NOT NULL,
	PRIMARY KEY("key")
);