# POSIX awk; LC_ALL=C makes escaped Unicode encoding deterministic.
# MODE, BASE, V_MODEL, V_TOKEN, V_BASE, V_CATALOG are supplied by the generator.
function fail(message) { print "Codex config unchanged: " message > "/dev/stderr"; exit 2 }
function trim(s) { sub(/^[ \t\r\n]+/, "", s); sub(/[ \t\r\n]+$/, "", s); return s }
function split_top(s, delimiter, out, clean,    i,c,q,stack,comment,piece,n,run,j) {
    for (i in out) delete out[i]
    n=0; q=""; stack=""; comment=0; piece=""
    for (i=1; i<=length(s); i++) {
        c=substr(s,i,1)
        if (comment) {
            if (c!="\n") { if (!clean) piece=piece c; continue }
            comment=0
        }
        if (q!="") {
            piece=piece c
            if (substr(q,1,1)=="\"" && c=="\\") { piece=piece substr(s,++i,1); continue }
            if (length(q)==1 && c=="\n") fail("newline in a single-line string")
            if (length(q)==1 && c==q) q=""
            else if (length(q)==3 && substr(s,i,3)==q) {
                run=3; while (substr(s,i+run,1)==c && run<5) run++
                piece=piece substr(s,i+1,run-1); i+=run-1; q=""
            }
            continue
        }
        if (c=="#") { comment=1; if (!clean) piece=piece c; continue }
        if (c=="\"" || c=="'") {
            q=c
            if (substr(s,i,3)==c c c) { q=c c c; piece=piece q; i+=2 } else piece=piece c
            continue
        }
        if (c=="[" || c=="{") stack=stack c
        if (c=="]" || c=="}") {
            if (substr(stack,length(stack),1)!=(c=="]" ? "[" : "{")) fail("unbalanced brackets")
            stack=substr(stack,1,length(stack)-1)
        }
        if (delimiter!="" && c==delimiter && stack=="") { out[++n]=piece; piece="" } else piece=piece c
    }
    if (q!="" || stack!="") fail("unterminated string or table")
    out[++n]=piece
    return n
}
function code(s,    a) { split_top(s,"",a,1); return trim(a[1]) }
function utf8(n) {
    if (n<0 || n>1114111 || (n>=55296 && n<=57343)) fail("invalid Unicode escape")
    if (n<128) return sprintf("%c",n)
    if (n<2048) return sprintf("%c%c",192+int(n/64),128+n%64)
    if (n<65536) return sprintf("%c%c%c",224+int(n/4096),128+int(n/64)%64,128+n%64)
    return sprintf("%c%c%c%c",240+int(n/262144),128+int(n/4096)%64,128+int(n/64)%64,128+n%64)
}
function string_value(s,    q,i,c,e,out,n,j,d,width) {
    s=trim(s); q=substr(s,1,1)
    if (q!="\"" && q!="'") return ""
    if (substr(s,length(s),1)!=q) fail("invalid quoted value")
    if (substr(s,1,3)==q q q) s=substr(s,4,length(s)-6); else s=substr(s,2,length(s)-2)
    if (q=="'") return s
    out=""
    for (i=1;i<=length(s);i++) {
        c=substr(s,i,1)
        if (c!="\\") { out=out c; continue }
        e=substr(s,++i,1)
        if (e=="u" || e=="U") {
            width=(e=="u" ? 4 : 8); n=0
            for(j=1;j<=width;j++) { d=index("0123456789abcdef",tolower(substr(s,++i,1)))-1; if(d<0) fail("invalid Unicode escape"); n=n*16+d }
            out=out utf8(n)
        } else if(e=="n") out=out "\n"
        else if(e=="r") out=out "\r"
        else if(e=="t") out=out "\t"
        else if(e=="b") out=out sprintf("%c",8)
        else if(e=="f") out=out sprintf("%c",12)
        else if(e=="\\" || e=="\"") out=out e
        else fail("unsupported string escape")
    }
    return out
}
function path(s,    a,n,i,k,result) {
    n=split_top(s,".",a,0); result=""
    for(i=1;i<=n;i++) {
        k=trim(a[i]); if(k !~ /^[A-Za-z0-9_-]+$/) {
            if(substr(k,1,1)!="\"" && substr(k,1,1)!="'") fail("invalid key")
            k=string_value(k)
        }
        if(index(k,S)) fail("unsupported control character in a key")
        result=result (i>1 ? S : "") k
    }
    return result
}
function quote(s,    i,c,result) {
    result="\""
    for(i=1;i<=length(s);i++) { c=substr(s,i,1)
        if(c=="\\" || c=="\"") result=result "\\" c
        else if(c=="\n") result=result "\\n"
        else if(c=="\r") result=result "\\r"
        else if(c=="\t") result=result "\\t"
        else result=result c
    }
    return result "\""
}
function key(s) { return s ~ /^[A-Za-z0-9_-]+$/ ? s : quote(s) }
function dotted(p,    a,n,i,result) { n=split(p,a,S); result=""; for(i=1;i<=n;i++) result=result (i>1 ? "." : "") key(a[i]); return result }
function managed(p) { return p=="features" || index(p,"features" S)==1 || p=="model_providers" || index(p,"model_providers" S)==1 }
function get_value(p) { return (p in F) ? F[p] : "" }
function set_value(p,v) { if(!(p in Seen)) { Seen[p]=1; Order[++Count]=p }; F[p]=v }
function put(p,v,    a,n,i,pair,k,value) {
    v=trim(v); if(v=="") fail("missing value")
    if(substr(v,1,1)=="{") {
        if(substr(v,length(v),1)!="}") fail("invalid inline table")
        Tables[p]=1; v=substr(v,2,length(v)-2)
        if(trim(v)=="") return
        n=split_top(v,",",a,0)
        for(i=1;i<=n;i++) {
            if(split_top(a[i],"=",pair,0)!=2) fail("invalid inline table field")
            put(p S path(pair[1]),pair[2])
        }
    } else {
        if(p in F) fail("duplicate setting")
        if(p=="features" || p=="model_providers" || (index(p,"model_providers" S)==1 && split(p,a,S)<3)) fail("expected a table")
        set_value(p,v)
    }
}
function parse(text,    a,n,i,raw,v,header,pair,p,array_table) {
    n=split_top(text,"\n",a,0); Section=""
    for(i=1;i<=n;i++) {
        raw=a[i]; v=code(raw)
        if(v=="") { if(trim(raw)!="" || !managed(Section)) R[++RC]=raw; continue }
        if(substr(v,1,1)=="[") {
            array_table=(substr(v,1,2)=="[[")
            header=substr(v,array_table ? 3 : 2,length(v)-(array_table ? 4 : 2))
            Section=path(header)
            if(managed(Section)) {
                if(array_table) fail("provider/feature array tables are not supported")
                if(Section in Headers) fail("duplicate table")
                Headers[Section]=1; Tables[Section]=1
            } else R[++RC]=raw
            continue
        }
        if(split_top(v,"=",pair,0)!=2) fail("invalid setting")
        p=(Section!="" ? Section S : "") path(pair[1])
        if(managed(p)) {
            put(p,pair[2])
            if(p==DK && raw ~ /# codex-lb-feature-owned[ \t]*$/) Discovery="owned"
            if(p==DK && raw ~ /# codex-lb-feature-was-false[ \t]*$/) Discovery="was-false"
        } else { R[++RC]=raw; RP[RC]=p; RV[RC]=trim(pair[2]); if(p=="model_provider") Active=string_value(pair[2]) }
    }
}
function remove_prefix(prefix,    p) { for(p in F) if(p==prefix || index(p,prefix S)==1) delete F[p]; for(p in Tables) if(p==prefix || index(p,prefix S)==1) delete Tables[p] }
function providers(    p,a,n) { for(p in F) { n=split(p,a,S); if(a[1]=="model_providers" && n>=3) Providers[a[2]]=1 }; for(p in Tables) { n=split(p,a,S); if(a[1]=="model_providers" && n>=2) Providers[a[2]]=1 } }
function is_relay(id,    prefix,p,a,n,url,token) {
    prefix="model_providers" S id; url=string_value(get_value(prefix S "base_url")); sub(/\/$/,"",url)
    token=string_value(get_value(prefix S "experimental_bearer_token"))
    if(url==BASE && url!="") return 1
    if(url ~ /\/backend-api\/codex$/ && token ~ /^sk-clb-/) return 1
    if(url ~ /\/backend-api\/codex$/) for(p in F) if(index(p,prefix S "auth" S)==1 && index(F[p],"codex-lb.key")) return 1
    for(p in F) { n=split(p,a,S); if(n==4 && a[1]=="model_providers" && a[2]==id && a[3]=="http_headers" && tolower(a[4])=="x-openai-actor-authorization" && string_value(F[p])=="codex-lb") return 1 }
    return 0
}
function setup(    p,id,only,n,a,prefix) {
    n=0; only=""; for(id in Providers) if(id!="openai" && id!="ollama" && id!="lmstudio") { n++; only=id }
    if(Active in Providers && Active!="openai" && Active!="ollama" && Active!="lmstudio") Selected=Active
    else if("openai_https" in Providers) Selected="openai_https"
    else Selected=(n==1 ? only : "openai_https")
    prefix="model_providers" S Selected
    remove_prefix(prefix S "auth"); delete F[prefix S "env_key"]; delete F[prefix S "env_key_instructions"]
    for(p in F) { n=split(p,a,S); if(n==4 && a[1]=="model_providers" && a[2]==Selected && (a[3]=="http_headers" || a[3]=="env_http_headers") && (tolower(a[4])=="authorization" || tolower(a[4])=="x-openai-actor-authorization")) delete F[p] }
    set_value(prefix S "name","\"OpenAI\""); set_value(prefix S "base_url",V_BASE)
    set_value(prefix S "model_catalog_url",V_CATALOG); set_value(prefix S "wire_api","\"responses\"")
    set_value(prefix S "experimental_bearer_token",V_TOKEN); set_value(prefix S "requires_openai_auth","true")
    set_value(prefix S "http_headers" S "x-openai-actor-authorization","\"codex-lb\"")
    set_value(prefix S "supports_websockets","false")
    if(Discovery=="") { if(!(DK in F)) Discovery="owned"; else if(F[DK]=="false") Discovery="was-false" }
    set_value(DK,"true")
}
function cleanup(    id,prefix,p,a,n,k,fields,remaining) {
    for(id in Providers) if(is_relay(id)) {
        Removed[id]=1; RemovedCount++; prefix="model_providers" S id
        for(p in F) if(index(p,prefix S "auth" S)==1 && index(F[p],"codex-lb.key")) { remove_prefix(prefix S "auth"); break }
        n=split("base_url model_catalog_url experimental_bearer_token requires_openai_auth wire_api supports_websockets",fields," ")
        for(k=1;k<=n;k++) delete F[prefix S fields[k]]
        for(p in F) {
            n=split(p,a,S)
            if(n==4 && a[1]=="model_providers" && a[2]==id && a[3]=="http_headers" && tolower(a[4])=="x-openai-actor-authorization" && string_value(F[p])=="codex-lb") delete F[p]
        }
        remaining=0; for(p in F) if(index(p,prefix S)==1 && p!=prefix S "name") remaining++
        for(p in Tables) if(index(p,prefix S)==1 && p!=prefix S "http_headers" && p!=prefix S "env_http_headers") remaining++
        if(!remaining) remove_prefix(prefix)
    }
    if(RemovedCount && Discovery=="owned") { delete F[DK]; Discovery="" }
    else if(RemovedCount && Discovery=="was-false") { F[DK]="false"; Discovery="" }
}
function render(    result,i,p,a,n,group,g,k,body,groups,gn,have) {
    if(MODE=="cleanup" && !RemovedCount) return Original
    result=""
    for(i=1;i<=RC;i++) {
        if(MODE=="setup" && (RP[i]=="model" || RP[i]=="model_provider")) continue
        n=split(RP[i],a,S)
        if(MODE=="cleanup" && (RP[i]=="model_provider" || (n==3 && a[1]=="profiles" && a[3]=="model_provider")) && string_value(RV[i]) in Removed) continue
        result=result R[i] "\n"
    }
    sub(/^\n+/,"",result); sub(/\n+$/,"",result)
    if(MODE=="setup") result="model = " V_MODEL "\nmodel_provider = " quote(Selected) "\n\n" result
    sub(/\n+$/,"",result)
    for(i=1;i<=Count;i++) if(Order[i] in F) {
        p=Order[i]; n=split(p,a,S); group=substr(p,1,length(p)-length(a[n])-1)
        if(!(group in GroupSeen)) { GroupSeen[group]=1; groups[++gn]=group }
    }
    # Preserve explicitly empty tables (including unrelated provider parameters).
    for(p in Tables) if(!(p in GroupSeen)) {
        have=0; for(k in F) if(index(k,p S)==1) { have=1; break }
        if(!have) groups[++gn]=p
    }
    for(g=1;g<=gn;g++) {
        group=groups[g]; result=result "\n\n[" dotted(group) "]\n"
        for(i=1;i<=Count;i++) if(Order[i] in F) {
            p=Order[i]; n=split(p,a,S)
            if(substr(p,1,length(p)-length(a[n])-1)!=group) continue
            result=result key(a[n]) " = " F[p]
            if(p==DK && Discovery!="") result=result " # codex-lb-feature-" Discovery
            result=result "\n"
        }
        sub(/\n+$/,"",result)
    }
    sub(/^\n+/,"",result); sub(/\n+$/,"",result)
    return result (result!="" ? "\n" : "")
}
BEGIN { S=sprintf("%c",28); DK="features" S "api_key_model_discovery" }
{ Original=Original $0 "\n"; line=$0; sub(/\r$/,"",line); if(NR==1) sub(/^\357\273\277/,"",line); Text=Text line "\n" }
END { parse(Text); providers(); if(MODE=="setup") setup(); else cleanup(); if(MODE=="cleanup" && !RemovedCount) exit 3; printf "%s",render() }
