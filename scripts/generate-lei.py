#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Generate random but valid Legal Entity Identifiers (LEIs)

LEI Format (ISO 17442):
- 20 alphanumeric characters
- Characters 1-4: LOU (Local Operating Unit) identifier
- Characters 5-18: Entity-specific identifier (14 characters)
- Characters 19-20: Check digits (MOD 97-10 algorithm)

Example: 549300FXRY59AB1V3S41
"""

import random
import string
import sys


def calculate_lei_check_digits(lei_base: str) -> str:
    """
    Calculate LEI check digits using MOD 97-10 algorithm (ISO 17442).

    Args:
        lei_base: First 18 characters of LEI (LOU + Entity identifier)

    Returns:
        Two-digit check digit string
    """
    # Append "00" temporarily for calculation
    temp_lei = lei_base + "00"

    # Replace letters with numbers (A=10, B=11, ..., Z=35)
    numeric_string = ""
    for char in temp_lei:
        if char.isdigit():
            numeric_string += char
        elif char.isalpha():
            # A=10, B=11, ..., Z=35
            numeric_string += str(ord(char.upper()) - ord('A') + 10)

    # Calculate MOD 97
    mod_result = int(numeric_string) % 97

    # Check digits = 98 - mod_result
    check_digits = 98 - mod_result

    # Pad with leading zero if needed
    return str(check_digits).zfill(2)


def generate_random_lei() -> str:
    """
    Generate a random but valid LEI.

    Returns:
        20-character LEI string with valid check digits
    """
    # Valid characters for LEI (alphanumeric, excluding I and O to avoid confusion)
    # Note: Some LEI implementations use all alphanumeric, some exclude I/O
    # We'll use uppercase letters and digits
    lei_chars = string.ascii_uppercase + string.digits

    # Generate LOU identifier (4 characters)
    # In practice, these are assigned by GLEIF, but we'll generate random ones
    # Common real LOUs start with specific prefixes (e.g., "5493" for GLEIF)
    lou = ''.join(random.choice(lei_chars) for _ in range(4))

    # Generate entity identifier (14 characters)
    entity_id = ''.join(random.choice(lei_chars) for _ in range(14))

    # Combine LOU and entity ID
    lei_base = lou + entity_id

    # Calculate check digits
    check_digits = calculate_lei_check_digits(lei_base)

    # Complete LEI
    lei = lei_base + check_digits

    return lei


def verify_lei(lei: str) -> bool:
    """
    Verify that an LEI has valid check digits.

    Args:
        lei: 20-character LEI string

    Returns:
        True if check digits are valid, False otherwise
    """
    if len(lei) != 20:
        return False

    # For verification: MOD 97 of entire LEI should equal 1
    # Replace letters with numbers (A=10, B=11, ..., Z=35)
    numeric_string = ""
    for char in lei:
        if char.isdigit():
            numeric_string += char
        elif char.isalpha():
            # A=10, B=11, ..., Z=35
            numeric_string += str(ord(char.upper()) - ord('A') + 10)

    # Calculate MOD 97 - should be 1 for valid LEI
    mod_result = int(numeric_string) % 97

    return mod_result == 1


def format_lei(lei: str) -> str:
    """
    Format LEI with spaces for readability: XXXX XXXX XXXX XXXX XX XX

    Args:
        lei: 20-character LEI string

    Returns:
        Formatted LEI string
    """
    return f"{lei[0:4]} {lei[4:8]} {lei[8:12]} {lei[12:16]} {lei[16:18]} {lei[18:20]}"


def main():
    """Generate and display random LEIs."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate random but valid Legal Entity Identifiers (LEIs)",
        epilog="""
Examples:
  %(prog)s -n 5              Generate 5 LEIs
  %(prog)s -n 3 --format     Generate 3 LEIs with formatted output
  %(prog)s -v ABCD...        Verify an existing LEI

Note: Generated LEIs use random LOU identifiers. Real LEIs are issued by
Local Operating Units (LOUs) accredited by the Global Legal Entity
Identifier Foundation (GLEIF).
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=10,
        help="Number of LEIs to generate (default: 10)"
    )
    parser.add_argument(
        "-f", "--format",
        action="store_true",
        help="Format LEIs with spaces for readability"
    )
    parser.add_argument(
        "-v", "--verify",
        type=str,
        metavar="LEI",
        help="Verify the check digits of an existing LEI"
    )

    args = parser.parse_args()

    # Verify mode
    if args.verify:
        lei = args.verify.replace(" ", "").upper()
        is_valid = verify_lei(lei)

        if is_valid:
            print(f"✓ Valid LEI: {format_lei(lei) if args.format else lei}")
            sys.exit(0)
        else:
            print(f"✗ Invalid LEI: {lei}")
            if len(lei) == 20:
                lei_base = lei[:18]
                correct_check = calculate_lei_check_digits(lei_base)
                print(f"  Expected check digits: {correct_check}")
                print(f"  Provided check digits: {lei[18:20]}")
            else:
                print(f"  LEI must be exactly 20 characters (got {len(lei)})")
            sys.exit(1)

    # Generation mode
    print(f"Generating {args.count} random LEI{'s' if args.count != 1 else ''}...\n")

    for i in range(args.count):
        lei = generate_random_lei()

        # Verify the generated LEI
        assert verify_lei(lei), f"Generated invalid LEI: {lei}"

        if args.format:
            print(f"{i+1:3d}. {format_lei(lei)}")
        else:
            print(f"{i+1:3d}. {lei}")

    print(f"\nAll {args.count} LEIs have valid check digits (MOD 97-10 verified)")


if __name__ == "__main__":
    main()
