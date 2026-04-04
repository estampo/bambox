fn main() {
    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .file("shim/shim.cpp")
        .compile("bambu_shim");

    // Link dl for dlopen/dlsym and pthread for threading
    println!("cargo:rustc-link-lib=dl");
    println!("cargo:rustc-link-lib=pthread");
    println!("cargo:rustc-link-lib=stdc++");
    println!("cargo:rerun-if-changed=shim/shim.cpp");
}
