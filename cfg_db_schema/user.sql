--系统用户信息表
CREATE TABLE "user" (
	"id"	INTEGER NOT NULL UNIQUE,
	"name"	TEXT,
	"pswd"	TEXT,
	"t"	TEXT,
	"role"	INTEGER DEFAULT 0,
	"area"	TEXT,
	"hack_info"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);