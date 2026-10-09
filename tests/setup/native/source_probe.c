/* DiskEd-owned read-only source-consumer fixture. Public USK C ABI only. */
#include "usk/usk_api.h"
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <io.h>

#define REQUEST_MAX 8192u
#define RESPONSE_MAX 1048576u
typedef struct Counts { size_t allocs; size_t frees; size_t live; } Counts;

static void* counted_alloc(void* user, usk_size size)
{
    Counts* counts = (Counts*)user;
    void* value;
    if (size > RESPONSE_MAX) return NULL;
    value = malloc((size_t)size);
    if (value != NULL) { ++counts->allocs; ++counts->live; }
    return value;
}

static void counted_free(void* user, void* value)
{
    Counts* counts = (Counts*)user;
    if (value != NULL) { ++counts->frees; --counts->live; free(value); }
}

static usk_string_view view(const char* value)
{
    usk_string_view result;
    result.data = value; result.size = value == NULL ? 0 : (usk_size)strlen(value);
    return result;
}

static int execute(usk_context* context, const char* name, const char* payload,
                   size_t bytes, usk_command_response_v1* response)
{
    usk_command_request_v1 request;
    memset(&request, 0, sizeof(request)); memset(response, 0, sizeof(*response));
    request.struct_size = sizeof(request); request.command_name = view(name);
    request.json_payload.data = payload; request.json_payload.size = bytes;
    request.dry_run = 1; response->struct_size = sizeof(*response);
    return usk_command_execute_v1(context, &request, response);
}

static char* copy_response(const usk_command_response_v1* response, size_t* bytes)
{
    char* copy;
    if (response->json_payload.data == NULL || response->json_payload.size == 0 ||
        response->json_payload.size > RESPONSE_MAX) return NULL;
    *bytes = (size_t)response->json_payload.size;
    copy = (char*)malloc(*bytes + 1u);
    if (copy == NULL) return NULL;
    memcpy(copy, response->json_payload.data, *bytes); copy[*bytes] = '\0';
    if (memchr(copy, '\0', *bytes) != NULL) { free(copy); return NULL; }
    return copy;
}

static int selftest(void)
{
    usk_context* context = NULL;
    usk_config_v1 config;
    usk_allocator_v1 allocator;
    usk_command_request_v1 request;
    usk_command_response_v1 response;
    Counts counts = {0, 0, 0};
    char* owned; size_t bytes = 0; int code;
    unsigned checks = 0;
    if (usk_abi_version_v1() != 65536u || sizeof(void*) != 8 || sizeof(usk_size) != 8 ||
        sizeof(usk_string_view) != 16 || sizeof(usk_config_v1) != 40 || sizeof(usk_allocator_v1) != 32 ||
        sizeof(usk_command_request_v1) != 48 || sizeof(usk_error_v1) != 48 || sizeof(usk_command_response_v1) != 80 ||
        USK_CONFIG_V1_BASE_SIZE != 16 || USK_CONFIG_V1_M1_SIZE != 24) return 10;
    ++checks;
    if (usk_context_create_v1(NULL, NULL) != USK_STATUS_INVALID_ARGUMENT) return 11;
    memset(&config, 0, sizeof(config)); config.struct_size = 8;
    if (usk_context_create_v1(&config, &context) != USK_STATUS_INVALID_ARGUMENT || context != NULL) return 12;
    ++checks;
    config.struct_size = USK_CONFIG_V1_BASE_SIZE;
    if (usk_context_create_v1(&config, &context) != USK_STATUS_OK || context == NULL) return 13;
    usk_context_destroy_v1(context); context = NULL; ++checks;
    memset(&allocator, 0, sizeof(allocator)); allocator.struct_size = sizeof(allocator);
    allocator.user = &counts; allocator.alloc = counted_alloc; allocator.free = counted_free;
    config.struct_size = sizeof(config); config.allocator = &allocator;
    if (usk_context_create_v1(&config, &context) != USK_STATUS_OK || context == NULL || counts.live != 1) return 14;
    ++checks;
    memset(&request, 0, sizeof(request)); memset(&response, 0, sizeof(response));
    request.struct_size = 8; request.command_name = view("policy.inspect"); response.struct_size = sizeof(response);
    if (usk_command_execute_v1(context, &request, &response) != USK_STATUS_INVALID_ARGUMENT) return 15;
    request.struct_size = sizeof(request);
    response.struct_size = 8; response.status = 12345;
    if (usk_command_execute_v1(context, &request, &response) != USK_STATUS_INVALID_ARGUMENT || response.status != 12345) return 16;
    ++checks;
    code = execute(context, "command_graph.inspect_v2", "{}", 2, &response);
    if (code != USK_STATUS_OK || response.status != code) return 17;
    owned = copy_response(&response, &bytes);
    if (owned == NULL || strstr(owned, "usk.command_graph.v2") == NULL) return 18;
    code = execute(context, "policy.inspect", "{}", 2, &response);
    if (code != USK_STATUS_OK || response.status != code || strstr(owned, "usk.command_graph.v2") == NULL) return 19;
    usk_context_destroy_v1(context); context = NULL;
    if (counts.live != 0 || counts.allocs != counts.frees || strstr(owned, "usk.command_graph.v2") == NULL) return 20;
    ++checks;
    printf("{\"schema\":\"org.disked.setup-source-selftest/1\",\"checks\":%u,\"abi\":65536,"
           "\"config_bytes\":%llu,\"request_bytes\":%llu,\"response_bytes\":%llu,"
           "\"context_allocations\":%llu,\"context_frees\":%llu,\"owned_graph_bytes\":%llu,"
           "\"borrowed_pointer_used_after_invalidation\":false,\"lifecycle_configured\":false}\n",
           checks, (unsigned long long)sizeof(config), (unsigned long long)sizeof(request),
           (unsigned long long)sizeof(response), (unsigned long long)counts.allocs,
           (unsigned long long)counts.frees, (unsigned long long)bytes);
    free(owned); return 0;
}

int main(int argc, char** argv)
{
    static const char* const commands[] = {"policy.inspect", "command_graph.inspect_v2", "install_local.inspect",
                                          "package.verify", "package.audit", "install_local.plan"};
    size_t i; int known = 0; char payload[REQUEST_MAX + 1u]; size_t bytes;
    usk_context* context = NULL; usk_config_v1 config; usk_allocator_v1 allocator;
    usk_command_response_v1 response; int code; int status;
    Counts counts = {0, 0, 0}; char* owned; size_t response_bytes = 0;
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 ||
        _setmode(_fileno(stdout), _O_BINARY) == -1) return 7;
#ifdef DISKED_SETUP_HOST_FIXTURE
    if (argc == 2 && strcmp(argv[1], "host.inspect") == 0) {
        printf("{\"schema\":\"org.disked.setup-host-fixture/1\",\"product_id\":\"org.disked\","
               "\"role\":\"H-read-only-fixture\",\"abi\":%u,\"contained_payloads\":[],"
               "\"embedded_final_payload_hash\":false,\"generic_package_verification\":false,"
               "\"live_lifecycle\":false,\"context_created\":false,"
               "\"source_revision\":\"%s\",\"source_state\":\"%s\",\"setup_revision\":\"%s\"}\n",
               (unsigned)usk_abi_version_v1(), DISKED_HOST_REVISION,
               DISKED_HOST_SOURCE_STATE, DISKED_HOST_SETUP_REVISION);
        return ferror(stdout) ? 6 : 0;
    }
#endif
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) return selftest();
    if (argc == 2) for (i = 0; i < sizeof(commands)/sizeof(commands[0]); ++i)
        if (strcmp(argv[1], commands[i]) == 0) known = 1;
    if (!known) {
        puts("{\"status\":\"refused\",\"reason\":\"command_not_in_read_only_probe\",\"context_created\":false}");
        return 2;
    }
    bytes = fread(payload, 1, sizeof(payload), stdin);
    if (ferror(stdin) || bytes == 0 || bytes > REQUEST_MAX || memchr(payload, '\0', bytes) != NULL) {
        puts("{\"status\":\"refused\",\"reason\":\"bounded_request_required\",\"context_created\":false}");
        return 2;
    }
    memset(&allocator, 0, sizeof(allocator)); allocator.struct_size = sizeof(allocator);
    allocator.user = &counts; allocator.alloc = counted_alloc; allocator.free = counted_free;
    memset(&config, 0, sizeof(config)); config.struct_size = sizeof(config); config.allocator = &allocator;
    if (usk_context_create_v1(&config, &context) != USK_STATUS_OK || context == NULL) return 3;
    code = execute(context, argv[1], payload, bytes, &response); status = response.status;
    owned = copy_response(&response, &response_bytes);
    /* The supplier view is invalidated here. Only our independently owned copy survives. */
    if (execute(context, "policy.inspect", "{}", 2, &response) != USK_STATUS_OK) return 4;
    usk_context_destroy_v1(context); context = NULL;
    if (owned == NULL || counts.live != 0 || counts.allocs != counts.frees) return 5;
    printf("{\"schema\":\"org.disked.setup-source-observation/1\",\"abi\":%u,\"provider_return\":%d,"
           "\"provider_response_status\":%d,\"borrowed_copy_bytes\":%llu,\"context_allocations\":%llu,"
           "\"context_frees\":%llu,\"lifecycle_configured\":false,\"response\":",
           (unsigned)usk_abi_version_v1(), code, status, (unsigned long long)response_bytes,
           (unsigned long long)counts.allocs, (unsigned long long)counts.frees);
    if (fwrite(owned, 1, response_bytes, stdout) != response_bytes) { free(owned); return 6; }
    free(owned); puts("}"); return ferror(stdout) ? 6 : 0;
}
