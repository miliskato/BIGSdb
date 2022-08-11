import logging


class DistanceMatrixQuery:
    def __init__(self, isolate_id: str, isolate_st: int, distance_threshold: int, distance_matrix_collection):
        self.isolate_id = isolate_id
        self.st = isolate_st
        self.distance_threshold = distance_threshold
        self.distance_matrix_collection = distance_matrix_collection
        self.distances_where_isolate_is_not = {}
        self.st_under_threshold = []

    def run_distance_query(self) -> list:
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Retrieving distances in the matrix")
        self.__get_isolate_distances()
        logging.info("Applying the distance threshold")
        self.__get_good_distances()
        return self.st_under_threshold

    def __get_isolate_distances(self) -> None:
        self.distances_where_isolate_is_not['I'] = self.distance_matrix_collection.find({'J': self.st})
        self.distances_where_isolate_is_not['J'] = self.distance_matrix_collection.find({'I': self.st})

    def __get_good_distances(self) -> None:
        for key in ['I', 'J']:
            for dist in self.distances_where_isolate_is_not[key]:
                if dist['Hamming_distance'] <= self.distance_threshold:
                    self.st_under_threshold.append(dist[key])
        self.st_under_threshold = list(dict.fromkeys(self.st_under_threshold))
