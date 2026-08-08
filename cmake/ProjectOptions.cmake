function(re_set_project_warnings target warnings_as_errors)
  set(msvc_warnings /W4 /permissive- /EHsc)
  set(gcc_clang_warnings
    -Wall
    -Wextra
    -Wpedantic
    -Wconversion
    -Wsign-conversion
    -Wshadow
    -Wnon-virtual-dtor
    -Wold-style-cast
    -Woverloaded-virtual
    -Wnull-dereference
    -Wdouble-promotion
    -Wformat=2
  )

  if(MSVC)
    target_compile_options(${target} PRIVATE ${msvc_warnings})
    if(warnings_as_errors)
      target_compile_options(${target} PRIVATE /WX)
    endif()
  else()
    target_compile_options(${target} PRIVATE ${gcc_clang_warnings})
    if(warnings_as_errors)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()
