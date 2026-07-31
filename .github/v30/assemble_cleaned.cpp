#include <windows.h>
#include <dxcapi.h>
#include <wrl/client.h>

#include <iomanip>
#include <iostream>

using Microsoft::WRL::ComPtr;

static int fail_with_hresult(
    const char *message,
    HRESULT hr)
{
    std::cerr
        << message
        << " HRESULT=0x"
        << std::hex
        << std::uppercase
        << static_cast<unsigned long>(hr)
        << std::endl;

    return 1;
}

int wmain(
    int argc,
    wchar_t **argv)
{
    if (argc != 3)
    {
        std::wcerr
  << L"Usage: assemble_cleaned.exe input.ll output.dxil"
  << std::endl;

        return 2;
    }

    const HRESULT init =
        CoInitializeEx(
  nullptr,
  COINIT_MULTITHREADED);

    const bool should_uninitialize =
        SUCCEEDED(init);

    if (
        FAILED(init) &&
        init != RPC_E_CHANGED_MODE)
    {
        return fail_with_hresult(
  "CoInitializeEx failed",
  init);
    }

    ComPtr<IDxcLibrary> library;

    HRESULT hr =
        DxcCreateInstance(
  CLSID_DxcLibrary,
  IID_PPV_ARGS(
      library.GetAddressOf()));

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "Create IDxcLibrary failed",
  hr);
    }

    ComPtr<IDxcAssembler> assembler;

    hr =
        DxcCreateInstance(
  CLSID_DxcAssembler,
  IID_PPV_ARGS(
      assembler.GetAddressOf()));

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "Create IDxcAssembler failed",
  hr);
    }

    UINT32 code_page = CP_UTF8;

    ComPtr<IDxcBlobEncoding> input;

    hr =
        library->CreateBlobFromFile(
  argv[1],
  &code_page,
  input.GetAddressOf());

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "Load input IR failed",
  hr);
    }

    ComPtr<IDxcOperationResult> result;

    hr =
        assembler->AssembleToContainer(
  input.Get(),
  result.GetAddressOf());

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "AssembleToContainer failed",
  hr);
    }

    HRESULT status = E_FAIL;

    hr = result->GetStatus(&status);

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "GetStatus failed",
  hr);
    }

    if (FAILED(status))
    {
        ComPtr<IDxcBlobEncoding> errors;

        if (
  SUCCEEDED(
      result->GetErrorBuffer(
          errors.GetAddressOf())) &&
  errors &&
  errors->GetBufferPointer() &&
  errors->GetBufferSize() > 0)
        {
  std::cerr.write(
      static_cast<const char *>(
          errors->GetBufferPointer()),
      static_cast<std::streamsize>(
          errors->GetBufferSize()));

  std::cerr << std::endl;
        }

        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "DXIL assembler rejected cleaned IR",
  status);
    }

    ComPtr<IDxcBlob> output;

    hr =
        result->GetResult(
  output.GetAddressOf());

    if (FAILED(hr))
    {
        if (should_uninitialize)
  CoUninitialize();

        return fail_with_hresult(
  "GetResult failed",
  hr);
    }

    if (
        !output ||
        !output->GetBufferPointer() ||
        output->GetBufferSize() == 0)
    {
        std::cerr
  << "Assembler returned an empty container."
  << std::endl;

        if (should_uninitialize)
  CoUninitialize();

        return 1;
    }

    HANDLE file =
        CreateFileW(
  argv[2],
  GENERIC_WRITE,
  0,
  nullptr,
  CREATE_ALWAYS,
  FILE_ATTRIBUTE_NORMAL,
  nullptr);

    if (file == INVALID_HANDLE_VALUE)
    {
        std::cerr
  << "CreateFileW failed. Win32="
  << GetLastError()
  << std::endl;

        if (should_uninitialize)
  CoUninitialize();

        return 1;
    }

    const DWORD size =
        static_cast<DWORD>(
  output->GetBufferSize());

    DWORD written = 0;

    const BOOL write_ok =
        WriteFile(
  file,
  output->GetBufferPointer(),
  size,
  &written,
  nullptr);

    const DWORD write_error =
        write_ok
  ? ERROR_SUCCESS
  : GetLastError();

    CloseHandle(file);

    if (
        !write_ok ||
        written != size)
    {
        std::cerr
  << "WriteFile failed. Win32="
  << write_error
  << " written="
  << written
  << " expected="
  << size
  << std::endl;

        if (should_uninitialize)
  CoUninitialize();

        return 1;
    }

    std::cout
        << "CLEANED_DXIL_BYTES="
        << output->GetBufferSize()
        << std::endl;

    std::cout
        << "DXIL_CLEANUP_ASSEMBLY_OK"
        << std::endl;

    if (should_uninitialize)
        CoUninitialize();

    return 0;
}