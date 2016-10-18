import numpy as np
import pytest

from lsh.cache import Cache
from lsh.minhash import MinHasher


@pytest.fixture
def default_hasher():
    return MinHasher(seeds=100)


@pytest.fixture
def default_cache(default_hasher):
    return Cache(default_hasher)


def is_nondecreasing(L):
    # http://stackoverflow.com/a/4983359/419338
    return all(x <= y for x, y in zip(L, L[1:]))


def test_hasher_json_serialisation(default_hasher, tmpdir):
    path = str(tmpdir.join("hasher.json"))

    default_hasher.to_json(path)
    loaded_hasher = MinHasher.from_json_file(path)

    doc = 'Once upon a time in a galaxy far far away and what not'
    np.testing.assert_array_equal(default_hasher.fingerprint(doc),
                                  loaded_hasher.fingerprint(doc))


def test_cache_json_serialisation(tmpdir, default_cache):
    path = str(tmpdir.join("cache.json"))

    # easy case- the bins array is empty
    default_cache.to_json(path)
    loaded_cache = Cache.from_json(path)

    # now add some data
    default_cache.update("This is a document", 0)
    loaded_cache.update("This is a document", 0)

    default_cache.to_json(path)
    loaded_cache = Cache.from_json(path)

    default_cache.update("The king of Denmark", 1)
    loaded_cache.update("The king of Denmark", 1)
    default_cache.update("The queen of Zerg", 2)
    loaded_cache.update("The queen of Zerg", 2)

    default_cache.to_json(path)
    loaded_cache = Cache.from_json(path)


@pytest.mark.parametrize("char_ngram", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("hashbytes", [4, 8])
@pytest.mark.parametrize("num_bands", [20, 40, 50])
@pytest.mark.parametrize("seed", range(3))
def test_cache(char_ngram, hashbytes, num_bands, seed):
    hasher = MinHasher(seeds=200, char_ngram=char_ngram,
                       hashbytes=hashbytes, random_state=seed)
    lsh = Cache(hasher, num_bands=num_bands)
    # very small band width => always find duplicates

    short_doc = 'This is a simple document'
    another_doc = 'Some text about animals.'
    long_doc = 'A much longer document that contains lots of information\
       different words. The document produces many more shingles.'

    assert not lsh.is_duplicate(short_doc)
    lsh.update(short_doc, 0)
    assert lsh.get_duplicates_of(short_doc) == {0}
    assert not lsh.is_duplicate(short_doc, doc_id=0)
    assert lsh.is_duplicate(short_doc)  # no id provided, compare by

    assert not lsh.is_duplicate(long_doc)
    lsh.update(long_doc, 1)
    lsh.update(another_doc, 2)

    # id is provided, so ignoree matches to self. the doc is therefore unique
    assert not lsh.is_duplicate(another_doc, doc_id=2)
    # w/o an id, the doc will match itself
    assert lsh.is_duplicate(another_doc)

    assert not lsh.is_duplicate(long_doc, doc_id=1)

    words = long_doc.split()
    long_doc_missing_word = ' '.join([words[0]] + words[2:])

    assert lsh.get_duplicates_of(long_doc_missing_word) == {1}
    assert lsh.is_duplicate(long_doc_missing_word)
    assert lsh.is_duplicate(long_doc + ' Word.')

    assert lsh.get_all_duplicates() == set()
    lsh.update(long_doc_missing_word, 3)
    assert lsh.get_all_duplicates() == {(1, 3)}

    lsh.update(long_doc_missing_word, 4)
    assert lsh.get_all_duplicates() == {(1, 3), (1, 4), (3, 4)}


mc_long_doc = "Jang MC Min Chul is a Protoss player from South Korea, who " \
              "last played for Trig  Esports before retiring. On May 23rd, " \
              "2016, MC announced his return to pro-gaming by joining CJ " \
              "Entus. He is currently "

mc_med_doc = "Jang MC Min Chul is a Protoss player from South Korea, who " \
             "last played for Trig Esports before retiring. He is currently "

mc_short_doc = "Jang MC Min Chul is currently "


@pytest.mark.parametrize("doc", [mc_long_doc, mc_med_doc, mc_short_doc])
def test_num_bands(doc):
    """
    add near-duplicate documents to three caches with different settings
    check that hashers with low band_width finds more matches (over 50 runs)
    """
    suffixes = ['teamless', 'retired', 'awesome', 'overweight']
    duplicates = []
    divisors_of_200 = [4, 10, 20, 25, 40, 50, 100]

    for seed in range(10):
        hasher = MinHasher(seeds=200, char_ngram=5, random_state=seed)
        caches = [Cache(hasher, num_bands=n) for n in divisors_of_200]

        for c in caches:
            c.update(doc + suffixes[0], 0)

        for s in suffixes[1:]:
            duplicates.append([c.is_duplicate(doc + s) for c in caches])

    sums = np.array(duplicates).sum(axis=0)
    print(sums)
    assert is_nondecreasing(sums)


def test_jaccard(default_hasher):
    assert default_hasher.jaccard("This is a doc", "This is a doc") == 1

    high_j = default_hasher.jaccard("This is a doc", "That is a doc")
    low_j = default_hasher.jaccard("This is a doc", "Cats in a tree")
    assert 0 <= low_j < high_j <= 1


@pytest.mark.parametrize("num_bands", [3, 6, 7, 9, 71, 99, 101])
def test_invalid_settings(num_bands, default_hasher):
    with pytest.raises(AssertionError):
        lsh = Cache(default_hasher, num_bands=num_bands)
        lsh.update('Hi', 1)
        lsh.get_duplicates_of('Hello')


def test_clear(default_cache):
    default_cache.update(mc_long_doc, 0)
    assert default_cache.is_duplicate(mc_long_doc)
    default_cache.clear()
    assert not default_cache.is_duplicate(mc_long_doc)
