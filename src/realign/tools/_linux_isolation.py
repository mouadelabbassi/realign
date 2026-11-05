"""Unprivileged Linux isolation: Landlock filesystem policy plus seccomp.

Fail closed on unsupported kernels/architectures. No permission-only fallback.
Kernel reference: docs.kernel.org/userspace-api/landlock.html.
"""
import ctypes as c
import errno
import os
import platform


def restrict(read_paths):
    if platform.machine().lower() not in ('x86_64','amd64'):
        raise OSError('unsupported seccomp architecture')
    libc=c.CDLL(None,use_errno=True)
    libc.syscall.restype=c.c_long
    abi=libc.syscall(444,0,0,1)
    if abi<3:
        raise OSError('Landlock ABI >=3 required')
    class Rules(c.Structure):
        _fields_=[('access',c.c_uint64)]
    class Beneath(c.Structure):
        _pack_=1
        _fields_=[('allowed',c.c_uint64),('parent',c.c_int32)]
    handled=(1<<15)-1
    rule=Rules(handled)
    fd=libc.syscall(444,c.byref(rule),c.sizeof(rule),0)
    if fd<0:
        raise OSError(c.get_errno(),'Landlock ruleset failed')
    try:
        for path in read_paths:
            p=os.open(path,os.O_PATH|os.O_CLOEXEC)
            try:
                access=(1<<2)|((1<<3) if os.path.isdir(path) else 0)
                entry=Beneath(access,p)
                if libc.syscall(445,fd,1,c.byref(entry),0)<0:
                    raise OSError(c.get_errno(),'Landlock rule failed')
            finally:
                os.close(p)
        if libc.prctl(38,1,0,0,0)!=0 or libc.syscall(446,fd,0)!=0:
            raise OSError(c.get_errno(),'Landlock enforcement failed')
    finally:
        os.close(fd)
    class Filter(c.Structure):
        _fields_=[('code',c.c_ushort),('jt',c.c_ubyte),('jf',c.c_ubyte),('k',c.c_uint32)]
    class Program(c.Structure):
        _fields_=[('len',c.c_ushort),('filter',c.POINTER(Filter))]
    f=[Filter(0x20,0,0,4),Filter(0x15,1,0,0xc000003e),Filter(0x06,0,0,0x80000000),
       Filter(0x20,0,0,0),Filter(0x45,0,1,0x40000000),
       Filter(0x06,0,0,0x00050000|errno.EPERM)]
    denied=[41,42,43,44,45,46,47,49,50,53,56,57,58,59,101,155,165,166,
            272,298,303,304,308,310,311,312,313,321,322,323,425,426,427,434,438]
    denied.remove(56)
    for number in denied:
        f.extend([Filter(0x15,0,1,number),Filter(0x06,0,0,0x00050000|errno.EPERM)])
    f.extend([Filter(0x15,0,1,435),Filter(0x06,0,0,0x00050000|errno.ENOSYS)])
    f.extend([Filter(0x15,0,4,56),Filter(0x20,0,0,16),Filter(0x45,1,0,0x10000),
              Filter(0x06,0,0,0x00050000|errno.EPERM),Filter(0x06,0,0,0x7fff0000),
              Filter(0x06,0,0,0x7fff0000)])
    array=(Filter*len(f))(*f)
    prog=Program(len(f),array)
    if libc.prctl(22,2,c.byref(prog),0,0)!=0:
        raise OSError(c.get_errno(),'seccomp enforcement failed')
    c.set_errno(0)
    if libc.syscall(0x40000027)!=-1 or c.get_errno()!=errno.EPERM:
        raise OSError('x32 syscall isolation failed')
    return 'LINUX_LANDLOCK_SECCOMP'
