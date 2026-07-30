# PEAD Blind-Custody Protocol

Protocol version: 1.0
Frozen in Phase: 0
Applies to: structural holdouts, D7, D8, and the final blind bank

## Purpose

This protocol prevents method development from observing or influencing claim-bearing holdout content. It separates scientific design, encrypted custody, method freeze, one-shot materialization, projection-only execution, and delayed label reveal.

## Repository and custody boundary

The development repository may contain only:

- universal holdout and domain interfaces;
- generic serialization and nonrevealing schema contracts;
- D7/D8 placeholder identities;
- canonical allocation configuration and its signed generated manifest;
- ciphertext, hashes, counts, and nonrevealing metadata;
- commitment-verification code that cannot generate claim-bearing content.

The custody workspace exclusively contains:

- claim-bearing generator and allocation implementation;
- structural mechanisms, logical forms, graph topologies, interactions, interventions, nuisances, and hidden seeds;
- D7/D8 generation logic, templates, vocabularies, surface distributions, feature mappings, nuisance transformations, allocation realizations, examples, labels, and adapter outputs;
- ambiguity proof inputs and complete certificate-generation logic;
- encryption keys and plaintext banks.

Concrete custody paths, keys, credentials, plaintext, and scientific content must never be committed to the development repository before the registered post-evaluation release point.

## Chronology

1. Phase 9A designs, reviews, hashes, signs, encrypts, and seals every substantive holdout component before any Phase 10 training, calibration result, or public-validation result.
2. Phase 10 may verify the signed design commitment but cannot read, modify, replace, rebalance, or regenerate the holdouts.
3. Phase 11 freezes methods, checkpoints, thresholds, prompts, environments, metrics, audits, and reports; verifies every precommitment; performs the single unlock; and one-shot materializes a content-addressed read-only bank.
4. Phase 12 performs no unlock or rematerialization. It streams cases from the immutable Phase 11 materialization.
5. Labels remain separately encrypted until each method decision and trace commitment is durable.

## Access and event order

For each case:

```text
encrypted case facts
  -> frozen AccessProfile projection
  -> method decision and trace commitment
  -> hidden label reveal to evaluator
  -> immutable outcome trace
  -> audit
```

A method receives only its registered projection. It never receives `WorldState`, plaintext labels, custody paths, encryption material, or an object with a back-reference to hidden truth.

## One-shot materialization

Materialization is authorized only by a complete signed freeze manifest. It must:

- verify all Phase 9A hashes before decryption;
- use one registered materialization ID;
- write content-addressed read-only case objects;
- preserve labels as a separate encrypted stream;
- append a signed event for every access and transformation;
- reproduce the same case hashes on a verification attempt or fail;
- reject any second unlock request for the same study version.

Phase 12 records the Phase 11 materialization ID in every run, case, projection, decision, trace, audit, and report manifest.

## Custody log

The append-only signed log records:

- actor or service identity;
- timestamp and monotonic sequence number;
- study, design-commitment, freeze, materialization, case, and projection identities;
- attempted action and authorization verdict;
- input and output hashes;
- decision-commit and label-reveal order;
- denied access and incident classification.

Missing, reordered, unsigned, or hash-inconsistent events invalidate the affected bank.

## Invalidating events

The blind bank is invalidated by:

- pre-freeze development access;
- source, commitment, ciphertext, or materialization hash mismatch;
- missing or altered custody event;
- key exposure;
- scientific redesign after commitment;
- non-one-shot mutation or a second unlock;
- direct method access to hidden content, labels, generator source, or custody implementation;
- D7/D8 implementation exposure before the registered release point.

Repair requires a new study version with new hidden seeds and encryption key when the scientific bank or confidentiality boundary may have been affected.

## Allowed Phase 11 actions

Phase 11 may verify, freeze, unlock once, materialize once, and audit contamination. It may not design or change a mechanism, grammar, topology, interaction, intervention, nuisance generator, domain template, seed allocation, distance, ambiguity rule, or quota.

## Evidence required for release

- signed Phase 9A design commitment;
- encrypted package index;
- signed method-freeze manifest;
- one-shot materialization record and immutable content hashes;
- projection and decision-before-label event logs;
- source-exposure and custody-denial audits;
- Phase 12 materialization-identity audit;
- post-evaluation release record for any custody source publication.
