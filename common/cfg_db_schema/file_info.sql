--文件信息记录
CREATE TABLE "file_info" (
	"id"	INTEGER NOT NULL UNIQUE,
	"fid"	TEXT NOT NULL,
	"uid"	INTEGER,
	"full_path"	TEXT NOT NULL,
	"timestamp"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);