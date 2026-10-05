#include "bootstrap.h"

int main() {
    disked::initialize_fake_provider();
    return 0; // A correctly linked poison provider must exit 97 before this.
}
