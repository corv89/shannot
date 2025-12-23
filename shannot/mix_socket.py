from .virtualizedproc import sigerror


class MixSocket:
    """Add (unimplemented) support for the socket and select modules.
    Should not really be used."""

    # extra functions from select and socket
    s_CMSG_LEN_wrapper = sigerror("CMSG_LEN_wrapper(i)i")
    s_CMSG_SPACE_wrapper = sigerror("CMSG_SPACE_wrapper(i)i")
    s_accept = sigerror("accept(ipp)i")
    s_accept4 = sigerror("accept4(ippi)i")
    s_bind = sigerror("bind(ipi)i")
    s_connect = sigerror("connect(ipi)i")
    s_free_pointer_to_signedp = sigerror("free_pointer_to_signedp(p)i")
    s_free_ptr_to_charp = sigerror("free_ptr_to_charp(p)i")
    s_freeaddrinfo = sigerror("freeaddrinfo(p)v")
    s_getaddrinfo = sigerror("getaddrinfo(pppp)i")
    s_gethostbyaddr = sigerror("gethostbyaddr(pii)p")
    s_gethostbyname = sigerror("gethostbyname(p)p")
    s_gethostname = sigerror("gethostname(pi)i")
    s_getnameinfo = sigerror("getnameinfo(pipipii)i")
    s_getpeername = sigerror("getpeername(ipp)i")
    s_getprotobyname = sigerror("getprotobyname(p)p")
    s_getservbyname = sigerror("getservbyname(pp)p")
    s_getservbyport = sigerror("getservbyport(ip)p")
    s_getsockname = sigerror("getsockname(ipp)i")
    s_getsockopt = sigerror("getsockopt(iiipp)i")
    s_inet_ntop = sigerror("inet_ntop(ippi)p")
    s_inet_pton = sigerror("inet_pton(ipp)i")
    s_listen = sigerror("listen(ii)i")
    s_memcpy_from_CCHARP_at_offset_and_size = sigerror(
        "memcpy_from_CCHARP_at_offset_and_size(ppii)i"
    )
    s_poll = sigerror("poll(pii)i")
    s_recv = sigerror("recv(ipii)i")
    s_recvfrom = sigerror("recvfrom(ipiipp)i")
    s_recvmsg_implementation = sigerror("recvmsg_implementation(iiiippppppppppp)i")
    s_send = sigerror("send(ipii)i")
    s_sendmsg_implementation = sigerror("sendmsg_implementation(ipippippppii)i")
    s_sendto = sigerror("sendto(ipiipi)i")
    s_setsockopt = sigerror("setsockopt(iiipi)i")
    s_shutdown = sigerror("shutdown(ii)i")
    s_socket = sigerror("socket(iii)i")
    s_socketpair = sigerror("socketpair(iiip)i")
