--系统用户信息表
CREATE TABLE "user" (
	"id"	INTEGER NOT NULL UNIQUE,
	"name"	TEXT,
	"t"	TEXT,
	"role"	INTEGER DEFAULT 0,
	"area"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);