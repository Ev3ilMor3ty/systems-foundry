// Systematic Reed-Solomon file fragments over GF(256), polynomial 0x11d.
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace sv {
using Bytes = std::vector<std::uint8_t>;
using Matrix = std::vector<Bytes>;
constexpr std::uint64_t max_file = 64ULL * 1024 * 1024;
constexpr std::size_t header_size = 64;

std::uint8_t mul(std::uint8_t a, std::uint8_t b) {
  unsigned x = a, y = b, result = 0;
  while (y) {
    if (y & 1U)
      result ^= x;
    y >>= 1;
    x <<= 1;
    if (x & 256U)
      x ^= 0x11dU;
  }
  return static_cast<std::uint8_t>(result);
}
std::uint8_t power(std::uint8_t a, unsigned n) {
  std::uint8_t result = 1;
  while (n) {
    if (n & 1U)
      result = mul(result, a);
    a = mul(a, a);
    n >>= 1;
  }
  return result;
}
std::uint32_t crc(const std::uint8_t *data, std::size_t size) {
  std::uint32_t result = 0xffffffffU;
  for (std::size_t i = 0; i < size; ++i) {
    result ^= data[i];
    for (unsigned bit = 0; bit < 8; ++bit)
      result = (result >> 1) ^ ((result & 1U) ? 0xedb88320U : 0U);
  }
  return ~result;
}
std::uint32_t crc(const Bytes &bytes) {
  return crc(bytes.data(), bytes.size());
}

Matrix invert(Matrix a) {
  const auto n = a.size();
  Matrix inverse(n, Bytes(n));
  for (std::size_t i = 0; i < n; ++i)
    inverse[i][i] = 1;
  for (std::size_t col = 0; col < n; ++col) {
    auto pivot = col;
    while (pivot < n && a[pivot][col] == 0)
      ++pivot;
    if (pivot == n)
      throw std::runtime_error("singular fragment matrix");
    std::swap(a[pivot], a[col]);
    std::swap(inverse[pivot], inverse[col]);
    const auto scale = power(a[col][col], 254);
    for (std::size_t j = 0; j < n; ++j) {
      a[col][j] = mul(a[col][j], scale);
      inverse[col][j] = mul(inverse[col][j], scale);
    }
    for (std::size_t row = 0; row < n; ++row) {
      if (row == col)
        continue;
      const auto factor = a[row][col];
      for (std::size_t j = 0; j < n; ++j) {
        a[row][j] ^= mul(factor, a[col][j]);
        inverse[row][j] ^= mul(factor, inverse[col][j]);
      }
    }
  }
  return inverse;
}

Matrix generator(unsigned k, unsigned n) {
  Matrix v(n, Bytes(k));
  for (unsigned i = 0; i < n; ++i)
    for (unsigned j = 0; j < k; ++j)
      v[i][j] = power(static_cast<std::uint8_t>(i + 1), j);
  const Matrix top(v.begin(), v.begin() + k);
  const auto inverse = invert(top);
  Matrix result(n, Bytes(k));
  for (unsigned i = 0; i < n; ++i)
    for (unsigned j = 0; j < k; ++j)
      for (unsigned t = 0; t < k; ++t)
        result[i][j] ^= mul(v[i][t], inverse[t][j]);
  return result;
}

void put(Bytes &b, std::size_t at, std::uint64_t value, unsigned size) {
  for (unsigned i = 0; i < size; ++i)
    b[at + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
std::uint64_t get(const Bytes &b, std::size_t at, unsigned size) {
  std::uint64_t value = 0;
  for (unsigned i = 0; i < size; ++i)
    value |= static_cast<std::uint64_t>(b[at + i]) << (8 * i);
  return value;
}

Bytes read(const std::filesystem::path &path, std::uint64_t cap) {
  std::ifstream file(path, std::ios::binary);
  if (!file)
    throw std::runtime_error("cannot open input: " + path.string());
  // Bound reads independently of file_size, including files that grow or
  // special files.
  Bytes result;
  std::array<char, 65536> block{};
  while (file) {
    file.read(block.data(), static_cast<std::streamsize>(block.size()));
    const auto count = static_cast<std::size_t>(file.gcount());
    if (result.size() + count > cap)
      throw std::runtime_error("input exceeds size limit");
    result.insert(result.end(), block.data(), block.data() + count);
  }
  if (!file.eof())
    throw std::runtime_error("input read failed");
  return result;
}

void write_new(const std::filesystem::path &path, const Bytes &bytes) {
  // Exclusive creation: never truncate an existing output, even in a path race.
#ifdef _WIN32
  std::FILE *file = nullptr;
  if (_wfopen_s(&file, path.c_str(), L"wbx") != 0)
    file = nullptr;
#else
  auto *file = std::fopen(path.c_str(), "wbx");
#endif
  if (!file)
    throw std::runtime_error("cannot create new output: " + path.string());
  const auto written = std::fwrite(bytes.data(), 1, bytes.size(), file);
  const auto closed = std::fclose(file);
  if (written != bytes.size() || closed != 0)
    throw std::runtime_error("output write failed; partial file may remain: " +
                             path.string());
}

struct Fragment {
  unsigned k{}, m{}, index{};
  std::uint64_t original_size{}, shard_size{};
  std::uint32_t original_crc{};
  std::array<std::uint8_t, 16> set_id{};
  Bytes data;
};

Fragment parse(const Bytes &blob) {
  if (blob.size() < header_size || std::memcmp(blob.data(), "FNDYRS01", 8) != 0)
    throw std::runtime_error("bad fragment magic or truncated header");
  if (get(blob, 52, 4) != crc(blob.data(), 52))
    throw std::runtime_error("header CRC mismatch");
  if (blob[11] != 0 || std::any_of(blob.begin() + 56, blob.begin() + 64,
                                   [](auto x) { return x != 0; }))
    throw std::runtime_error("reserved header bytes must be zero");
  Fragment f;
  f.k = blob[8];
  f.m = blob[9];
  f.index = blob[10];
  f.original_size = get(blob, 12, 8);
  f.shard_size = get(blob, 20, 8);
  f.original_crc = static_cast<std::uint32_t>(get(blob, 28, 4));
  std::copy_n(blob.begin() + 32, 16, f.set_id.begin());
  if (f.k < 2 || f.k > 16 || f.m < 1 || f.m > 8 || f.index >= f.k + f.m ||
      f.original_size > max_file)
    throw std::runtime_error("fragment metadata outside supported limits");
  const auto expected_size =
      std::max<std::uint64_t>(1, (f.original_size + f.k - 1) / f.k);
  if (f.shard_size != expected_size ||
      blob.size() != header_size + expected_size)
    throw std::runtime_error("fragment length mismatch");
  f.data.assign(blob.begin() + header_size, blob.end());
  if (get(blob, 48, 4) != crc(f.data))
    throw std::runtime_error("payload CRC mismatch");
  return f;
}

void encode(const std::filesystem::path &input,
            const std::filesystem::path &directory, unsigned k, unsigned m) {
  if (k < 2 || k > 16 || m < 1 || m > 8)
    throw std::runtime_error("data count must be 2..16 and parity count 1..8");
  const auto original = read(input, max_file);
  const auto size = std::max<std::size_t>(1, (original.size() + k - 1) / k);
  Matrix data(k, Bytes(size));
  for (std::size_t i = 0; i < original.size(); ++i)
    data[i / size][i % size] = original[i];
  const auto matrix = generator(k, k + m);
  std::array<std::uint8_t, 16> id{};
  std::random_device random;
  for (auto &b : id)
    b = static_cast<std::uint8_t>(random());
  if (!std::filesystem::create_directory(directory))
    throw std::runtime_error("output directory must be new");
  const auto original_crc = crc(original);
  for (unsigned i = 0; i < k + m; ++i) {
    Bytes payload(size);
    for (unsigned j = 0; j < k; ++j) {
      if (matrix[i][j] == 0)
        continue;
      // Precompute one field multiplication table per coefficient, not per
      // byte.
      std::array<std::uint8_t, 256> table{};
      for (unsigned value = 0; value < 256; ++value)
        table[value] = mul(matrix[i][j], static_cast<std::uint8_t>(value));
      for (std::size_t b = 0; b < size; ++b)
        payload[b] ^= table[data[j][b]];
    }
    Bytes blob(header_size);
    std::memcpy(blob.data(), "FNDYRS01", 8);
    blob[8] = static_cast<std::uint8_t>(k);
    blob[9] = static_cast<std::uint8_t>(m);
    blob[10] = static_cast<std::uint8_t>(i);
    put(blob, 12, original.size(), 8);
    put(blob, 20, size, 8);
    put(blob, 28, original_crc, 4);
    std::copy(id.begin(), id.end(), blob.begin() + 32);
    put(blob, 48, crc(payload), 4);
    put(blob, 52, crc(blob.data(), 52), 4);
    blob.insert(blob.end(), payload.begin(), payload.end());
    write_new(directory / ("shard-" + std::to_string(i) + ".sv"), blob);
  }
  std::cout << "{\"data\":" << k << ",\"parity\":" << m
            << ",\"bytes\":" << original.size() << ",\"shard_bytes\":" << size
            << ",\"recover_from\":" << k << "}\n";
}

void recover(const std::filesystem::path &output,
             const std::vector<std::string> &paths) {
  if (paths.size() > 24)
    throw std::runtime_error("at most 24 input fragments");
  std::vector<Fragment> fragments;
  std::array<bool, 24> seen{};
  for (const auto &path : paths) {
    Fragment f;
    try {
      f = parse(read(path, max_file / 2 + header_size));
    } catch (const std::exception &error) {
      std::cerr << "skipping " << path << ": " << error.what() << '\n';
      continue;
    }
    if (!fragments.empty()) {
      const auto &first = fragments.front();
      if (f.k != first.k || f.m != first.m ||
          f.original_size != first.original_size ||
          f.shard_size != first.shard_size ||
          f.original_crc != first.original_crc || f.set_id != first.set_id)
        throw std::runtime_error("fragments belong to different sets");
    }
    if (seen[f.index])
      throw std::runtime_error("duplicate fragment index");
    seen[f.index] = true;
    fragments.push_back(std::move(f));
  }
  if (fragments.empty() || fragments.size() < fragments[0].k)
    throw std::runtime_error("not enough valid distinct fragments");
  const auto &first = fragments[0];
  const auto matrix = generator(first.k, first.k + first.m);
  Matrix selected;
  for (unsigned i = 0; i < first.k; ++i)
    selected.push_back(matrix[fragments[i].index]);
  const auto inverse = invert(selected);
  Bytes original(static_cast<std::size_t>(first.original_size));
  for (unsigned i = 0; i < first.k; ++i) {
    Bytes decoded(static_cast<std::size_t>(first.shard_size));
    for (unsigned j = 0; j < first.k; ++j) {
      std::array<std::uint8_t, 256> table{};
      for (unsigned value = 0; value < 256; ++value)
        table[value] = mul(inverse[i][j], static_cast<std::uint8_t>(value));
      for (std::size_t b = 0; b < decoded.size(); ++b)
        decoded[b] ^= table[fragments[j].data[b]];
    }
    const auto offset = static_cast<std::size_t>(i * first.shard_size);
    if (offset < original.size())
      std::copy_n(decoded.begin(),
                  std::min(decoded.size(), original.size() - offset),
                  original.begin() + static_cast<std::ptrdiff_t>(offset));
  }
  if (crc(original) != first.original_crc)
    throw std::runtime_error("recovered file CRC mismatch; output not written");
  write_new(output, original);
  std::cout << "{\"recovered\":true,\"bytes\":" << original.size()
            << ",\"valid_fragments\":" << fragments.size() << "}\n";
}

unsigned count(const char *text) {
  const std::string input(text);
  if (input.empty() || input.size() > 2 ||
      !std::all_of(input.begin(), input.end(),
                   [](char c) { return c >= '0' && c <= '9'; }))
    throw std::runtime_error("fragment count must be a small positive integer");
  return static_cast<unsigned>(std::stoul(input));
}
} // namespace sv

int main(int argc, char **argv) {
  try {
    if (argc == 2 && std::string(argv[1]) == "--help") {
      std::cout
          << "shardvault encode INPUT NEW_DIRECTORY DATA_COUNT "
             "PARITY_COUNT\nshardvault recover NEW_OUTPUT SHARD...\nEach valid "
             "set can recover from any DATA_COUNT distinct fragments.\nLimits: "
             "64 MiB input, 2..16 data + 1..8 parity. CRC32 detects accidental "
             "damage, not malicious changes.\n";
    } else if (argc == 6 && std::string(argv[1]) == "encode") {
      sv::encode(argv[2], argv[3], sv::count(argv[4]), sv::count(argv[5]));
    } else if (argc >= 4 && std::string(argv[1]) == "recover") {
      sv::recover(argv[2], std::vector<std::string>(argv + 3, argv + argc));
    } else
      throw std::runtime_error("invalid arguments; use --help");
  } catch (const std::exception &error) {
    std::cerr << "shardvault: " << error.what() << '\n';
    return 1;
  }
}
