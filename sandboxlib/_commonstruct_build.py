import cffi
ffibuilder = cffi.FFI()

ffibuilder.cdef("""
    #define DT_REG ...
    #define DT_DIR ...

    typedef int... dev_t;
    typedef int... ino_t;
    typedef int... mode_t;
    typedef int... nlink_t;
    typedef int... uid_t;
    typedef int... gid_t;
    typedef int... off_t;
    typedef int... time_t;
    typedef int... suseconds_t;

    struct stat {
       dev_t     st_dev;         /* ID of device containing file */
       ino_t     st_ino;         /* Inode number */
       mode_t    st_mode;        /* File type and mode */
       nlink_t   st_nlink;       /* Number of hard links */
       uid_t     st_uid;         /* User ID of owner */
       gid_t     st_gid;         /* Group ID of owner */
       dev_t     st_rdev;        /* Device ID (if special file) */
       off_t     st_size;        /* Total size, in bytes */
       time_t    st_atime;       /* last access, integer part only */
       time_t    st_mtime;       /* last modification, integer part only */
       time_t    st_ctime;       /* last status change, integer part only */
       ...;
    };

    struct dirent {
       ino_t          d_ino;       /* Inode number */
       off_t          d_off;       /* Not an offset; see below */
       unsigned short d_reclen;    /* Length of this record */
       unsigned char  d_type;      /* Type of file; not supported
                                      by all filesystem types */
       char           d_name[...]; /* Null-terminated filename */
       ...;
    };

    struct timeval {
       time_t      tv_sec;     /* seconds */
       suseconds_t tv_usec;    /* microseconds */
    };
""")

ffibuilder.set_source("sandboxlib._commonstruct_cffi", """

    #include <sys/time.h>
    #include <sys/types.h>
    #include <sys/stat.h>
    #include <unistd.h>
    #include <dirent.h>

""")

if __name__ == '__main__':
    ffibuilder.compile(verbose=True)
